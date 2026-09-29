"""Read-only evidence for one explicitly selected account; never output secrets."""
import argparse
import json

from sqlalchemy import select, func

from app import clock
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.models import User, ClassRoom, FaceSample, RecognitionTask, LoginSession


def snapshot(session, student_no):
    user = session.scalar(select(User).where(User.student_no == student_no))
    if user is None:
        return {'account_found': False}
    classroom = session.get(ClassRoom, user.class_id) if user.class_id else None
    faces = session.scalars(select(FaceSample).where(FaceSample.user_id == user.id).order_by(FaceSample.id)).all()
    tasks = session.scalars(select(RecognitionTask).where(RecognitionTask.owner_user_id == user.id).order_by(RecognitionTask.created_at.desc()).limit(10)).all()
    return {
        'account_found': True,
        'user': {'id': user.id, 'student_no': user.student_no, 'name': user.name,
                 'class': classroom.name if classroom else None, 'status': user.status, 'role': user.role},
        'photos': [{'id': f.id, 'status': f.status, 'dimension': f.dimension,
                    'embedding_bytes': len(f.embedding), 'model_version': f.model_version} for f in faces],
        'recent_tasks': [{'type': t.type, 'status': t.status, 'result_code': t.result_code,
                          'created_at': t.created_at.isoformat()} for t in tasks],
        'active_login_sessions': session.scalar(select(func.count()).select_from(LoginSession).where(
            LoginSession.user_id == user.id, LoginSession.expires_at > clock.utc_now())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--student-no', required=True, help='Only inspect this account')
    args = parser.parse_args()
    engine = make_engine(Settings.from_env())
    try:
        with make_session_factory(engine)() as session:
            print(json.dumps(snapshot(session, args.student_no), ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
