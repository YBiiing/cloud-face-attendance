from datetime import datetime
from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, UTCDateTime
from app.clock import utc_now


class RecognitionTask(Base):
    __tablename__='recognition_tasks'
    __table_args__=(UniqueConstraint('scope','request_key',name='uq_task_request'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    type: Mapped[str]=mapped_column(String(20))
    status: Mapped[str]=mapped_column(String(20),default='PENDING',index=True)
    owner_user_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'),index=True)
    session_id: Mapped[int|None]=mapped_column(ForeignKey('attendance_sessions.id'),index=True)
    scope: Mapped[str]=mapped_column(String(80))
    request_key: Mapped[str]=mapped_column(String(64))
    request_digest: Mapped[str]=mapped_column(String(64))
    token_hash: Mapped[str]=mapped_column(String(64))
    image_path: Mapped[str|None]=mapped_column(String(255))
    payload: Mapped[dict]=mapped_column(JSON,default=dict)
    result_code: Mapped[str|None]=mapped_column(String(40))
    created_at: Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)
    received_at: Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)
    expires_at: Mapped[datetime]=mapped_column(UTCDateTime(),index=True)
    started_at: Mapped[datetime|None]=mapped_column(UTCDateTime())
    finished_at: Mapped[datetime|None]=mapped_column(UTCDateTime())
    lease_until: Mapped[datetime|None]=mapped_column(UTCDateTime())
    attempt_id: Mapped[str|None]=mapped_column(String(36))
    attempts: Mapped[int]=mapped_column(default=0)
