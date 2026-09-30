"""Logical MySQL + referenced-photo backup. Restore only into an empty test DB.

Backups contain personal information and password hashes. Keep them private.
Models and APP_SECRET are deliberately not embedded in the archive.
"""
import argparse
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import zipfile

from sqlalchemy import select, text, LargeBinary
from app.config import Settings
from app.database import Base, UTCDateTime, make_engine, make_session_factory
from app.models import FaceLibraryState, FaceSample, RecognitionTask
from app.services.uploads import stored_path

PHOTO = re.compile(r'uploads/[0-9a-f]{32}\.image\Z')


def tables():
    return list(Base.metadata.sorted_tables)


def encode(table, row):
    result=dict(row)
    for column in table.columns:
        value=result[column.name]
        if value is None:continue
        if isinstance(column.type, LargeBinary):result[column.name]=base64.b64encode(value).decode('ascii')
        elif isinstance(column.type, UTCDateTime):result[column.name]=value.isoformat()
    return result


def decode(table, row):
    if set(row)!=set(table.columns.keys()):raise ValueError('Backup column mismatch')
    result=dict(row)
    for column in table.columns:
        value=result[column.name]
        if value is None:continue
        if isinstance(column.type, LargeBinary):result[column.name]=base64.b64decode(value,validate=True)
        elif isinstance(column.type, UTCDateTime):
            parsed=datetime.fromisoformat(value)
            if parsed.tzinfo is None:raise ValueError('Backup timestamps must have timezone')
            result[column.name]=parsed
    return result


def export_bundle(factory, storage, destination):
    destination=Path(destination)
    # Exclusive creation prevents accidental replacement of a previous backup.
    with destination.open('xb') as output:
        try:
            with factory.begin() as db, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
                # Shares the first lock with enrollment and cleanup. Keep it
                # until all referenced bytes have been copied from the snapshot.
                db.scalar(select(FaceLibraryState).where(FaceLibraryState.id==1).with_for_update())
                revision=db.scalar(text('SELECT version_num FROM alembic_version'))
                data={table.name:[encode(table,row) for row in db.execute(select(table)).mappings()] for table in tables()}
                references=set();required=set()
                for face in data['face_samples']:
                    references.add(face['image_path'])
                    if face['status']=='ACTIVE':required.add(face['image_path'])
                for task in data['recognition_tasks']:
                    if task['image_path']:
                        references.add(task['image_path'])
                        if task['status'] in {'PENDING','RUNNING'}:required.add(task['image_path'])
                checksums={}
                for relative in sorted(references):
                    if not PHOTO.fullmatch(relative):raise ValueError('Unmanaged photo reference')
                    path=stored_path(storage,relative)
                    if not path.is_file():
                        if relative in required:raise ValueError('Required photo is missing')
                        continue
                    payload=path.read_bytes();name='photos/'+relative
                    archive.writestr(name,payload);checksums[name]=hashlib.sha256(payload).hexdigest()
                payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
                archive.writestr('data.json',payload);checksums['data.json']=hashlib.sha256(payload).hexdigest()
                archive.writestr('manifest.json',json.dumps({'format':1,'revision':revision,'sha256':checksums}))
            return {'tables':len(data),'rows':sum(map(len,data.values())),'photos':len(checksums)-1}
        except Exception:
            output.close();destination.unlink(missing_ok=True)
            raise


def restore_bundle(factory, storage, source, settings):
    if settings.environment!='test' or settings.mysql_database!='face_attendance_test':
        raise ValueError('Restore is restricted to an empty isolated test database')
    root=Path(storage)
    if root.is_symlink() or (root/'uploads').is_symlink():raise ValueError('Storage symlinks are forbidden')
    root.mkdir(parents=True,exist_ok=True)
    if any(path.is_file() or path.is_symlink() for path in root.rglob('*')):
        raise ValueError('Restore target storage must be empty')
    created=[]
    with zipfile.ZipFile(source) as archive:
        entries=archive.infolist()
        if len({item.filename for item in entries})!=len(entries):raise ValueError('Duplicate archive entries')
        if sum(item.file_size for item in entries)>1024**3:raise ValueError('Backup exceeds 1 GiB safety limit')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest['format']!=1:raise ValueError('Unsupported backup format')
        expected=set(manifest['sha256'])|{'manifest.json'}
        if expected!={item.filename for item in entries}:raise ValueError('Unexpected archive entry')
        payloads={}
        for name,digest in manifest['sha256'].items():
            if name!='data.json' and not (name.startswith('photos/') and PHOTO.fullmatch(name[7:])):
                raise ValueError('Unsafe archive path')
            payload=archive.read(name)
            if hashlib.sha256(payload).hexdigest()!=digest:raise ValueError('Backup checksum mismatch')
            payloads[name]=payload
        data=json.loads(payloads.pop('data.json'))
        if set(data)!={table.name for table in tables()}:raise ValueError('Backup table mismatch')
        decoded={table.name:[decode(table,row) for row in data[table.name]] for table in tables()}
        for face in decoded['face_samples']:
            if face['status']=='ACTIVE' and 'photos/'+face['image_path'] not in payloads:raise ValueError('Active photo missing')
        for task in decoded['recognition_tasks']:
            if task['image_path'] and task['status'] in {'PENDING','RUNNING'} and 'photos/'+task['image_path'] not in payloads:
                raise ValueError('Pending task photo missing')
        try:
            with factory.begin() as db:
                if db.scalar(text('SELECT version_num FROM alembic_version'))!=manifest['revision']:
                    raise ValueError('Migration revision mismatch')
                for table in tables():
                    rows=db.execute(select(table).with_for_update()).mappings().all()
                    if table.name=='face_library_state':
                        if len(rows)!=1 or rows[0]['id']!=1 or rows[0]['version']!=0:raise ValueError('Target is not a fresh database')
                    elif rows:raise ValueError('Target database is not empty')
                db.execute(FaceLibraryState.__table__.delete())
                for table in tables():
                    if decoded[table.name]:db.execute(table.insert(),decoded[table.name])
                for name,payload in payloads.items():
                    path=stored_path(root,name[7:]);path.parent.mkdir(parents=True,exist_ok=True)
                    with path.open('xb') as output:
                        created.append(path)
                        output.write(payload)
            return {'restored_rows':sum(map(len,decoded.values())),'restored_photos':len(created)}
        except Exception:
            for path in created:path.unlink(missing_ok=True)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['export','restore'])
    parser.add_argument('--file',type=Path,required=True)
    parser.add_argument('--confirm-empty-test-database',action='store_true')
    args=parser.parse_args()
    if args.action=='restore' and not args.confirm_empty_test_database:parser.error('Explicit empty-test-database confirmation required')
    settings=Settings.from_env();engine=make_engine(settings);factory=make_session_factory(engine)
    try:
        result=export_bundle(factory,settings.storage_dir,args.file) if args.action=='export' else restore_bundle(factory,settings.storage_dir,args.file,settings)
        print(json.dumps(result))
    finally:engine.dispose()


if __name__=='__main__':main()
