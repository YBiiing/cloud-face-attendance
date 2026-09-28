from datetime import datetime
from sqlalchemy import ForeignKey,String
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base,UTCDateTime
from app.clock import utc_now


class AttendanceSession(Base):
    __tablename__='attendance_sessions'
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(100))
    class_id:Mapped[int]=mapped_column(ForeignKey('classes.id'),index=True)
    public_code:Mapped[str]=mapped_column(String(64),unique=True)
    starts_at:Mapped[datetime]=mapped_column(UTCDateTime())
    ends_at:Mapped[datetime]=mapped_column(UTCDateTime())
    closed_at:Mapped[datetime|None]=mapped_column(UTCDateTime())
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_at:Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)


class SessionMember(Base):
    __tablename__='session_members'
    session_id:Mapped[int]=mapped_column(ForeignKey('attendance_sessions.id'),primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
