from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select, func, and_

from app import clock
from app.errors import AppError
from app.models import AttendanceRecord, AttendanceSession, SessionMember, RecognitionTask, User
from app.security import current_user, db_session
from app.services.time_policy import session_status

router = APIRouter(prefix='/api/records', tags=['records'])


@router.get('/sessions')
def accessible_sessions(response: Response, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100),
                        actor=Depends(current_user), db=Depends(db_session)):
    response.headers['Cache-Control'] = 'no-store'
    query = select(AttendanceSession)
    if actor.role != 'ADMIN':
        query = query.join(SessionMember).where(SessionMember.user_id == actor.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(AttendanceSession.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {'items': [{'id': row.id, 'title': row.title, 'starts_at': row.starts_at,
                       'status': session_status(row, clock.utc_now())} for row in rows], 'total': total, 'page': page}


@router.get('')
def records(response: Response, session_id: int | None = Query(None, gt=0), page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100), actor=Depends(current_user), db=Depends(db_session)):
    response.headers['Cache-Control'] = 'no-store'
    if actor.role == 'ADMIN' and session_id is not None:
        row = db.get(AttendanceSession, session_id)
        if not row:
            raise AppError('NOT_FOUND', '签到场次不存在', 404)
        expected = db.scalar(select(func.count()).select_from(SessionMember).where(SessionMember.session_id == row.id))
        attended = db.scalar(select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.session_id == row.id))
        now = clock.utc_now()
        pending = db.scalar(select(func.count()).select_from(RecognitionTask).where(
            RecognitionTask.session_id == row.id, RecognitionTask.type == 'CHECKIN',
            RecognitionTask.status.in_(['PENDING', 'RUNNING']), RecognitionTask.expires_at > now))
        query = (select(User, AttendanceRecord).select_from(SessionMember)
                 .join(User, User.id == SessionMember.user_id)
                 .outerjoin(AttendanceRecord, and_(AttendanceRecord.session_id == SessionMember.session_id,
                                                   AttendanceRecord.user_id == SessionMember.user_id))
                 .where(SessionMember.session_id == row.id).order_by(User.student_no, User.id))
        rows = db.execute(query.offset((page-1)*page_size).limit(page_size)).all()
        return {'mode': 'roster', 'session_title': row.title, 'page': page, 'total': expected,
                'summary': {'expected': expected, 'attended': attended, 'absent': expected-attended,
                            'pending_tasks': pending, 'finalized': session_status(row, now) == 'CLOSED' and pending == 0},
                'items': [{'user_id': user.id, 'name': user.name, 'student_no': user.student_no,
                           'attended': record is not None, 'received_at': record.received_at if record else None,
                           'confirmed_at': record.confirmed_at if record else None} for user, record in rows]}
    query = select(AttendanceRecord, AttendanceSession.title, User.name, User.student_no).join(
        AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id).join(User, User.id == AttendanceRecord.user_id)
    if actor.role != 'ADMIN':
        query = query.where(AttendanceRecord.user_id == actor.id)
    if session_id is not None:
        query = query.where(AttendanceRecord.session_id == session_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(AttendanceRecord.received_at.desc(), AttendanceRecord.id.desc())
                      .offset((page-1)*page_size).limit(page_size)).all()
    return {'mode': 'records', 'page': page, 'total': total, 'summary': None,
            'items': [{'id': record.id, 'session_id': record.session_id, 'session_title': title,
                       'name': name, 'student_no': number, 'attended': True,
                       'received_at': record.received_at, 'confirmed_at': record.confirmed_at}
                      for record, title, name, number in rows]}
