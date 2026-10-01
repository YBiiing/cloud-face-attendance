import hashlib
import json
import zipfile
from types import SimpleNamespace
import pytest
from scripts.backup_data import restore_bundle, tables
from contextlib import contextmanager
from unittest.mock import MagicMock
from sqlalchemy.exc import OperationalError


def test_restore_rejects_other_environment_and_path_traversal(tmp_path):
    with pytest.raises(ValueError,match='restricted'):
        restore_bundle(None,tmp_path/'storage',tmp_path/'missing',SimpleNamespace(environment='local',mysql_database='face_attendance'))
    archive=tmp_path/'bad.zip';payload=b'bad'
    with zipfile.ZipFile(archive,'w') as bundle:
        name='photos/../../escape'
        bundle.writestr(name,payload)
        bundle.writestr('manifest.json',json.dumps({'format':1,'sha256':{name:hashlib.sha256(payload).hexdigest()}}))
    with pytest.raises(ValueError,match='Unsafe archive path'):
        restore_bundle(None,tmp_path/'storage',archive,SimpleNamespace(environment='test',mysql_database='face_attendance_test'))
    assert not (tmp_path/'escape').exists()


@pytest.mark.parametrize('commit_started', [False, True])
def test_restore_keeps_photos_if_commit_outcome_unknown(tmp_path, commit_started):
    photo = 'photos/uploads/'+'a'*32+'.image'; content = b'test photo'
    data = json.dumps({table.name: [] for table in tables()}).encode()
    archive = tmp_path/'restore.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        payloads = {'data.json': data, photo: content}
        for name, payload in payloads.items(): bundle.writestr(name, payload)
        bundle.writestr('manifest.json', json.dumps({'format': 1, 'revision': 'test', 'sha256': {
            name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}}))
    db = MagicMock(); db.scalar.return_value = 'test'
    def execute(statement):
        result = MagicMock()
        result.mappings.return_value.all.return_value = ([{'id': 1, 'version': 0}]
            if str(statement).startswith('SELECT face_library_state.') else [])
        return result
    db.execute.side_effect = execute
    if not commit_started: db.flush.side_effect = ValueError('confirmed before commit')
    class Factory:
        @contextmanager
        def begin(self):
            yield db
            raise OperationalError('COMMIT', {}, Exception('lost acknowledgement'))
    with pytest.raises((OperationalError, ValueError)):
        restore_bundle(Factory(), tmp_path/'storage', archive,
                       SimpleNamespace(environment='test', mysql_database='face_attendance_test'))
    target = tmp_path/'storage'/photo[7:]
    assert target.exists() is commit_started
    if commit_started: assert target.read_bytes() == content
