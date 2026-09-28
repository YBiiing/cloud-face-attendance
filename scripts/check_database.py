"""Non-destructive MySQL smoke checks; all inserted test records roll back."""
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.models import ClassRoom, User


def main():
    engine = make_engine(Settings.from_env())
    factory = make_session_factory(engine)
    marker = "smoke-" + uuid4().hex[:20]
    try:
        with factory() as session:
            classroom = ClassRoom(name=marker)
            session.add(classroom)
            session.flush()
            session.add(User(student_no=marker, name="临时验证", class_id=classroom.id, password_hash="not-a-login-hash"))
            session.flush()
            try:
                with session.begin_nested():
                    session.add(User(student_no=marker, name="重复记录", class_id=classroom.id, password_hash="not-a-login-hash"))
                    session.flush()
            except IntegrityError:
                pass
            else:
                raise AssertionError("Student number unique constraint missing")
            session.rollback()
        with factory() as session:
            assert session.scalar(select(ClassRoom).where(ClassRoom.name == marker)) is None
            assert session.scalar(select(User).where(User.student_no == marker)) is None
        print("PASS: MySQL uniqueness and transaction rollback; no smoke records retained")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
