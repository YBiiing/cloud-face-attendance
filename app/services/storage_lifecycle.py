"""Conservative cleanup: UUID uploads only, minimum one-day grace period."""
from datetime import timedelta, timezone, datetime
import re
from sqlalchemy import select
from app import clock
from app.models import FaceLibraryState, FaceSample, RecognitionTask
from app.services.uploads import stored_path

MANAGED = re.compile(r'[0-9a-f]{32}\.image\Z')
TERMINAL = {'SUCCEEDED', 'REJECTED', 'FAILED'}


def cleanup(factory, root, *, apply=False, retention_hours=24):
    if retention_hours < 24:
        raise ValueError('Retention must be at least 24 hours')
    root = root.resolve(); uploads = root/'uploads'
    if uploads.is_symlink() or (uploads.exists() and uploads.resolve().parent != root):
        raise ValueError('Uploads directory must not be a symlink')
    cutoff = clock.utc_now()-timedelta(hours=retention_hours)
    report = {'mode': 'apply' if apply else 'preview', 'eligible': [], 'removed': [], 'protected': 0, 'ignored': 0}
    if not uploads.exists(): return report
    for path in sorted(uploads.iterdir()):
        if path.is_symlink() or not path.is_file() or not MANAGED.fullmatch(path.name):
            report['ignored'] += 1; continue
        relative = 'uploads/'+path.name
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > cutoff:
            report['protected'] += 1; continue
        with factory.begin() as db:
            # Same first lock as enrollment/face replacement. Do not unlink a
            # sample while another transaction can turn that task into ACTIVE.
            db.scalar(select(FaceLibraryState).where(FaceLibraryState.id == 1).with_for_update())
            tasks = db.scalars(select(RecognitionTask).where(RecognitionTask.image_path == relative).with_for_update()).all()
            faces = db.scalars(select(FaceSample).where(FaceSample.image_path == relative).with_for_update()).all()
            if any(face.status == 'ACTIVE' for face in faces) or any(
                task.status not in TERMINAL or task.finished_at is None or task.finished_at > cutoff for task in tasks):
                report['protected'] += 1; continue
            checked = stored_path(root, relative)
            if checked != path or path.is_symlink(): raise ValueError('Storage path changed')
            report['eligible'].append(relative)
            if apply:
                checked.unlink(missing_ok=True)
                for task in tasks: task.image_path = None
                report['removed'].append(relative)
    return report
