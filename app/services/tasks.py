from datetime import timedelta
import hashlib
import hmac
import json
from uuid import UUID, uuid4
from sqlalchemy import select

from app import clock
from app.errors import AppError
from app.models.tasks import RecognitionTask
from app.security import token_hash

TERMINAL={'SUCCEEDED','REJECTED','FAILED'}


def validate_key(raw):
    try:
        parsed=UUID(raw)
        if parsed.version!=4: raise ValueError
        return str(parsed)
    except (ValueError,TypeError,AttributeError):
        raise AppError('INVALID_REQUEST','请提供有效的随机请求键',422) from None


def task_token(secret,task_id,key):
    return hmac.new(secret.encode(),f'task:{task_id}:{key}'.encode(),hashlib.sha256).hexdigest()


def request_digest(secret,fields):
    return hmac.new(secret.encode(),json.dumps(fields,sort_keys=True,ensure_ascii=False).encode(),hashlib.sha256).hexdigest()


def find_replay(session,scope,key,digest):
    existing=session.scalar(select(RecognitionTask).where(RecognitionTask.scope==scope,RecognitionTask.request_key==token_hash(key)))
    if existing and not hmac.compare_digest(existing.request_digest,digest):
        raise AppError('IDEMPOTENCY_CONFLICT','同一请求键不能用于不同内容',409)
    return existing


def new_task(secret,scope,key,digest,kind,owner=None,image_path=None,payload=None,received_at=None):
    task_id=str(uuid4()); now=received_at or clock.utc_now()
    token=task_token(secret,task_id,key)
    return RecognitionTask(id=task_id,type=kind,status='PENDING',owner_user_id=owner,
        scope=scope,request_key=token_hash(key),request_digest=digest,token_hash=token_hash(token),
        image_path=image_path,payload=payload or {},created_at=now,received_at=now,
        expires_at=now+timedelta(minutes=5),attempts=0)


def accepted(task,secret,key):
    return {'task_id':task.id,'task_token':task_token(secret,task.id,key),'status':task.status,'poll_url':f'/api/tasks/{task.id}'}


def dispatch(task_id):
    from app.jobs.celery_app import celery_app
    try:
        celery_app.send_task('attendance.process',args=[task_id],retry=False)
    except Exception:
        # The persisted PENDING task will be redelivered by the scheduler.
        return False
    return True
