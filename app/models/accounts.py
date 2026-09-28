from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


def utc_now():
    return datetime.now(timezone.utc)


class ClassRoom(Base):
    __tablename__ = "classes"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(Enum("ACTIVE", "DISABLED"), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(Enum("STUDENT", "ADMIN"), default="STUDENT")
    status: Mapped[str] = mapped_column(Enum("PENDING", "ACTIVE", "DISABLED"), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
