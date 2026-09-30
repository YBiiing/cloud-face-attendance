import hashlib
import json
import zipfile
from types import SimpleNamespace
import pytest
from scripts.backup_data import restore_bundle


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
