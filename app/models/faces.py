from datetime import datetime
from sqlalchemy import ForeignKey, String, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, UTCDateTime
from app.clock import utc_now


class FaceSample(Base):
    __tablename__='face_samples'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    image_path: Mapped[str]=mapped_column(String(255))
    embedding: Mapped[bytes]=mapped_column(LargeBinary)
    dimension: Mapped[int]=mapped_column(default=512)
    dtype: Mapped[str]=mapped_column(String(20),default='float32-le')
    model_version: Mapped[str]=mapped_column(String(100))
    status: Mapped[str]=mapped_column(String(20),default='ACTIVE',index=True)
    created_at: Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)


class FaceLibraryState(Base):
    __tablename__='face_library_state'
    id: Mapped[int]=mapped_column(primary_key=True)
    version: Mapped[int]=mapped_column(default=0)
    updated_at: Mapped[datetime]=mapped_column(UTCDateTime(),default=utc_now)
