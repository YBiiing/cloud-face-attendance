from datetime import datetime
from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint, String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, UTCDateTime


class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    __table_args__ = (
        UniqueConstraint('session_id', 'user_id', name='uq_attendance_person'),
        ForeignKeyConstraint(['session_id', 'user_id'], ['session_members.session_id', 'session_members.user_id'], name='fk_record_member'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('recognition_tasks.id'), unique=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime())
    confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    score: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(100))
