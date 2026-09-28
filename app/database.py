from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import URL, create_engine
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import Settings


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    impl = DATETIME(fsp=6)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetime must include timezone")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


def make_engine(settings: Settings):
    url = URL.create("mysql+pymysql", username=settings.mysql_user,
                     password=settings.mysql_password, host=settings.mysql_host,
                     port=settings.mysql_port, database=settings.mysql_database,
                     query={"charset": "utf8mb4"})
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800,
                         pool_size=5, max_overflow=5, pool_timeout=5,
                         hide_parameters=True,
                         connect_args={"connect_timeout": 3, "read_timeout": 5,
                                       "write_timeout": 5, "init_command": "SET time_zone = '+00:00'"})


def make_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory):
    with factory.begin() as session:
        yield session
