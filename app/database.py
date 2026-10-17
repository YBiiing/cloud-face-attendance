from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import URL, create_engine,event
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import Settings
from app.services.dependency_dns import resolve_host


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


def make_engine(settings: Settings, *, probe: bool = False):
    url = URL.create("mysql+pymysql", username=settings.mysql_user,
                     password=settings.mysql_password, host=settings.mysql_host,
                     port=settings.mysql_port, database=settings.mysql_database,
                     query={"charset": "utf8mb4"})
    engine=create_engine(url, pool_pre_ping=not probe, pool_recycle=1800,
                         pool_size=1 if probe else 5, max_overflow=0 if probe else 5, pool_timeout=1,
                         hide_parameters=True,
                         connect_args={"connect_timeout": 1, "read_timeout": 1 if probe else 2,
                                       "write_timeout": 1 if probe else 2, "init_command": "SET time_zone = '+00:00'"})
    @event.listens_for(engine,'do_connect')
    def bounded_address(dialect,record,args,parameters):
        try:parameters['host']=resolve_host(settings.mysql_host)
        except OSError:raise dialect.dbapi.OperationalError(2003,'Database address unavailable') from None
    return engine


def make_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory):
    with factory.begin() as session:
        yield session
