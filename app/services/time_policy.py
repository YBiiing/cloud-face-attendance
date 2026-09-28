def effective_end(session):
    return min(session.ends_at,session.closed_at) if session.closed_at else session.ends_at


def session_status(session,now):
    if now>=effective_end(session):return 'CLOSED'
    if now<session.starts_at:return 'SCHEDULED'
    return 'OPEN'


def eligible_time(session,received_at):
    return session.starts_at<=received_at<effective_end(session)
