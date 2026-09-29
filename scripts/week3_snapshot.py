"""Read-only MySQL evidence for a selected attendance session; no face/token data."""
import argparse
import json
from sqlalchemy import select, func
from app import clock
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.models import AttendanceSession, SessionMember, AttendanceRecord, RecognitionTask, User
from app.services.time_policy import session_status


def snapshot(db, session_id):
    row = db.get(AttendanceSession, session_id)
    if row is None:
        return {'session_found': False}
    now = clock.utc_now()
    expected = db.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id == row.id))
    attended = db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == row.id))
    pending = db.scalar(select(func.count()).select_from(RecognitionTask).where(
        RecognitionTask.session_id == row.id, RecognitionTask.type == 'CHECKIN',
        RecognitionTask.status.in_(['PENDING', 'RUNNING']), RecognitionTask.expires_at > now))
    counts = db.execute(select(RecognitionTask.status, func.count()).where(
        RecognitionTask.session_id == row.id, RecognitionTask.type == 'CHECKIN').group_by(RecognitionTask.status)).all()
    records = db.execute(select(AttendanceRecord, User.name, User.student_no).join(
        User, User.id == AttendanceRecord.user_id).where(AttendanceRecord.session_id == row.id)
        .order_by(AttendanceRecord.id).limit(100)).all()
    tasks = db.scalars(select(RecognitionTask).where(RecognitionTask.session_id == row.id, RecognitionTask.type == 'CHECKIN')
                      .order_by(RecognitionTask.created_at.desc()).limit(20)).all()
    return {'session_found': True, 'session_id': row.id, 'title': row.title,
            'status': session_status(row, now), 'expected': expected, 'attended': attended, 'absent': expected-attended,
            'pending_tasks': pending, 'finalized': session_status(row, now) == 'CLOSED' and pending == 0,
            'task_counts': dict(counts), 'record_limit': 100, 'recent_task_limit': 20,
            'records': [{'name': name, 'student_no': number, 'task_id': record.task_id,
                         'received_at': record.received_at.isoformat(), 'confirmed_at': record.confirmed_at.isoformat()}
                        for record, name, number in records],
            'recent_tasks': [{'task_id': task.id, 'status': task.status, 'result_code': task.result_code,
                              'received_at': task.received_at.isoformat()} for task in tasks]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id', required=True, type=int)
    args = parser.parse_args()
    if args.session_id < 1: parser.error('session-id must be positive')
    engine = make_engine(Settings.from_env())
    try:
        with make_session_factory(engine)() as db:
            print(json.dumps(snapshot(db, args.session_id), ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
