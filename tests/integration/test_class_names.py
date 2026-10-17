from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import delete, select, func
from sqlalchemy.exc import IntegrityError

from app.models import ClassRoom
from tests.integration.test_auth import accounts, sign_in


def test_duplicate_class_name_returns_conflict(client, accounts):
    headers=sign_in(client,accounts,'admin')
    name='Class-'+uuid4().hex
    try:
        created=client.post('/api/classes',json={'name':name},headers=headers)
        assert created.status_code==201
        for duplicate in [name,'  '+name+'  ',name.lower()]:
            response=client.post('/api/classes',json={'name':duplicate},headers=headers)
            assert response.status_code==409
            assert response.json()['error']['code']=='CLASS_NAME_EXISTS'
        with accounts['factory']() as db:
            assert db.scalar(select(func.count()).select_from(ClassRoom).where(ClassRoom.name==name))==1
    finally:
        with accounts['factory'].begin() as db:
            db.execute(delete(ClassRoom).where(ClassRoom.name==name))


def test_database_serializes_competing_class_names(accounts):
    name='Race-'+uuid4().hex
    barrier=Barrier(2)

    def insert():
        try:
            with accounts['factory'].begin() as db:
                assert db.scalar(select(ClassRoom.id).where(ClassRoom.name==name)) is None
                barrier.wait(timeout=10)
                db.add(ClassRoom(name=name))
            return 'created'
        except IntegrityError as error:
            assert 'uq_classes_name' in str(error.orig)
            return 'conflict'

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(insert) for _ in range(2)]
            assert sorted(f.result(timeout=20) for f in futures)==['conflict','created']
        with accounts['factory']() as db:
            assert db.scalar(select(func.count()).select_from(ClassRoom).where(ClassRoom.name==name))==1
    finally:
        with accounts['factory'].begin() as db:
            db.execute(delete(ClassRoom).where(ClassRoom.name==name))
