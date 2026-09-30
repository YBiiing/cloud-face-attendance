from sqlalchemy import select
from app import clock
from app.models import AttendanceRecord, AttendanceSession, SessionMember, RecognitionTask, FaceLibraryState, User
from app.services.time_policy import eligible_time
from app.services.retry import retry_transaction


@retry_transaction
def finish_checkin(factory, task_id, attempt, gallery_version, match, rejection, model_version):
    """Return False only if the caller must reload the gallery and rematch.

    Lock order: gallery -> task -> attendance session -> user. Model inference
    and vector comparison happen outside this transaction. Record and terminal
    task result commit together; the database also enforces per-session uniqueness.
    """
    with factory.begin() as db:
        state = db.scalar(select(FaceLibraryState).where(FaceLibraryState.id == 1).with_for_update())
        task = db.scalar(select(RecognitionTask).where(RecognitionTask.id == task_id).with_for_update())
        now = clock.utc_now()
        if not task or task.status != 'RUNNING' or task.attempt_id != attempt:
            return True
        if task.expires_at <= now:
            task.status = 'FAILED'; task.result_code = 'TASK_TIMEOUT'; task.finished_at = now
            return True
        if state.version != gallery_version:
            return False
        row = db.scalar(select(AttendanceSession).where(AttendanceSession.id == task.session_id).with_for_update())
        code = rejection
        if not row or not eligible_time(row, task.received_at):
            code = 'SESSION_ENDED'
        if code is None:
            user = db.scalar(select(User).where(User.id == match.user_id).with_for_update())
            if not user or user.status != 'ACTIVE':
                code = 'USER_UNAVAILABLE'
            elif db.get(SessionMember, (row.id, user.id)) is None:
                code = 'NOT_IN_ROSTER'
            else:
                existing = db.scalar(select(AttendanceRecord).where(
                    AttendanceRecord.session_id == row.id, AttendanceRecord.user_id == user.id))
                code = 'ALREADY_CHECKED_IN' if existing else 'CHECKED_IN'
                if not existing:
                    db.add(AttendanceRecord(session_id=row.id, user_id=user.id, task_id=task.id,
                        received_at=task.received_at, confirmed_at=now, score=match.score, model_version=model_version))
        task.result_code = code
        task.status = 'SUCCEEDED' if code in {'CHECKED_IN', 'ALREADY_CHECKED_IN'} else 'REJECTED'
        task.finished_at = now
        return True
