import pytest
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
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def session(settings):
    engine = make_engine(settings)
    with make_session_factory(engine)() as session:
        yield session
        session.rollback()
    engine.dispose()
