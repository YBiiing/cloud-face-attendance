from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
from app import clock
from app.services import capacity
from app.errors import AppError


def test_atomic_queue_limit_and_release(client, monkeypatch):
    key = 'test-capacity:'+uuid4().hex
    monkeypatch.setattr(capacity, 'KEY', key)
    redis = client.app.state.redis
    deadline = clock.utc_now()+timedelta(minutes=1)
    def submit(_):
        task_id = str(uuid4())
        try:
            capacity.reserve(redis, task_id, deadline, limit=5)
            return task_id
        except AppError as error:
            assert error.code == 'QUEUE_FULL'
            return None
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            admitted = [item for item in pool.map(submit, range(12)) if item]
        assert len(admitted) == 5 and redis.zcard(key) == 5
        capacity.release(redis, admitted[0])
        assert submit(0) is not None and redis.zcard(key) == 5
    finally:
        redis.delete(key)
