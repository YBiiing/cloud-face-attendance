import pytest
from ipaddress import IPv4Address
from uuid import uuid4
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.database import make_engine, make_session_factory


@pytest.fixture(scope="session")
def settings():
    config = Settings.from_env()
    if config.environment != "test" or config.mysql_database != "face_attendance_test":
        pytest.exit("Refusing tests outside isolated face_attendance_test database")
    return config


@pytest.fixture
def client(settings):
    # Independent scenarios must not share rate-limit budgets. Within a test,
    # requests still use the same source address and all normal limits apply.
    address=str(IPv4Address(0x0A000000 | (uuid4().int & 0x00FFFFFF)))
    with TestClient(create_app(settings),client=(address,50000)) as client:
        yield client


@pytest.fixture
def session(settings):
    engine = make_engine(settings)
    with make_session_factory(engine)() as session:
        yield session
        session.rollback()
    engine.dispose()
