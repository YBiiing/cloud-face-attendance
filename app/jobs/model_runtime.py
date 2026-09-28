import os
import socket
import threading
import time
from redis import Redis
from app.config import Settings
from app.face.engine import FaceEngine

_engine=None


def get_engine():
    global _engine
    if _engine is None:
        settings=Settings.from_env()
        _engine=FaceEngine(settings.model_dir)
        version=_engine.version
        def heartbeat():
            client=Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2)
            key=f'worker:model:{socket.gethostname()}:{os.getpid()}'
            while True:
                try: client.set(key,version,ex=20)
                except Exception: pass
                time.sleep(5)
        threading.Thread(target=heartbeat,daemon=True).start()
    return _engine
