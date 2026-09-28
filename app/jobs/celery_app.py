import os
from celery import Celery

celery_app=Celery('attendance',broker=os.environ['REDIS_URL'],include=['app.jobs.worker'])
celery_app.conf.update(task_serializer='json',accept_content=['json'],
    task_ignore_result=True,worker_prefetch_multiplier=1,task_acks_late=True,
    task_reject_on_worker_lost=True,broker_connection_retry_on_startup=True,
    broker_transport_options={'visibility_timeout':180},task_time_limit=120,
    task_soft_time_limit=110,timezone='UTC',enable_utc=True)
