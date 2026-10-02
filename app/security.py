import hashlib
import hmac
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import Request, Depends
from sqlalchemy import select

from app import clock
from app.errors import AppError
from app.models import User, LoginSession

COOKIE = 'attendance_session'


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64*1024*1024)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, expected = stored.split('$')
        if scheme != 'scrypt': return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(request: Request) -> str:
    token = request.cookies.get(COOKIE, '')
    return hmac.new(request.app.state.settings.app_secret.encode(), ('csrf:'+token).encode(), hashlib.sha256).hexdigest()


def db_session(request: Request):
    with request.app.state.sessions() as session:
        yield session


def check_origin(request: Request):
    origin = request.headers.get('origin')
    if origin:
        parsed = urlsplit(origin)
        if (parsed.scheme, parsed.netloc) != (request.url.scheme, request.url.netloc):
            raise AppError('FORBIDDEN', '请求来源不允许', 403)
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise AppError('FORBIDDEN', '请求来源不允许', 403)


def current_user(request: Request, session=Depends(db_session)) -> User:
    raw = request.cookies.get(COOKIE)
    if not raw: raise AppError('UNAUTHENTICATED', '请先登录', 401)
    login = session.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(raw), LoginSession.expires_at > clock.utc_now()))
    user = session.get(User, login.user_id) if login else None
    if not user or user.status != 'ACTIVE': raise AppError('UNAUTHENTICATED', '请重新登录', 401)
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf_token(request)):
            raise AppError('FORBIDDEN', '页面已过期，请刷新后重试', 403)
    return user


def admin_user(user=Depends(current_user)):
    if user.role != 'ADMIN': raise AppError('FORBIDDEN', '仅老师可操作', 403)
    return user


def rate_limit(request: Request, action: str, limit: int = 20, seconds: int = 60):
    ip = request.client.host if request.client else 'unknown'
    key = f'rate:{action}:{token_hash(ip)}'
    script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"
    try:
        count = request.app.state.redis.eval(script, 1, key, seconds)
    except Exception:
        raise AppError('SERVICE_UNAVAILABLE', '服务暂时不可用', 503) from None
    if count > limit: raise AppError('RATE_LIMITED', '操作过于频繁，请稍后再试', 429)
