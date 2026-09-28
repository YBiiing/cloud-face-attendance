import secrets
from datetime import timedelta
import hmac
import hashlib
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy import select, delete

from app import clock
from app.models import User, LoginSession
from app.schemas.accounts import LoginInput, user_data
from app.security import COOKIE, hash_password, verify_password, token_hash, csrf_token, db_session, current_user, check_origin, rate_limit
from app.errors import AppError

router = APIRouter(prefix='/api', tags=['accounts'])
DUMMY_HASH = hash_password('unused-timing-placeholder')


@router.post('/auth/login')
def login(data: LoginInput, request: Request, response: Response, session=Depends(db_session)):
    check_origin(request); rate_limit(request, 'login')
    user = session.scalar(select(User).where(User.student_no == data.student_no))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not valid or not user or user.status != 'ACTIVE':
        raise AppError('INVALID_CREDENTIALS', '账号或密码错误，或尚未完成注册', 401)
    old = request.cookies.get(COOKIE)
    if old: session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old)))
    raw = secrets.token_urlsafe(32)
    session.add(LoginSession(user_id=user.id, token_hash=token_hash(raw), expires_at=clock.utc_now()+timedelta(hours=12)))
    session.commit()
    response.set_cookie(COOKIE, raw, max_age=43200, httponly=True, secure=request.app.state.settings.cookie_secure, samesite='lax', path='/')
    response.headers['Cache-Control'] = 'no-store'
    csrf = hmac.new(request.app.state.settings.app_secret.encode(), ('csrf:'+raw).encode(), hashlib.sha256).hexdigest()
    return {'user':user_data(user), 'csrf_token':csrf}


@router.get('/me')
def me(request: Request, response: Response, user=Depends(current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return {'user':user_data(user), 'csrf_token':csrf_token(request)}


@router.post('/auth/logout', status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), session=Depends(db_session)):
    session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(request.cookies[COOKIE])))
    session.commit()
    response.delete_cookie(COOKIE, path='/', secure=request.app.state.settings.cookie_secure, httponly=True, samesite='lax')
