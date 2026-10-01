"""应用入口：python -m uvicorn app.main:create_app --factory。"""

from pathlib import Path
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from redis import Redis

from app.schemas.health import LiveResponse
from app.config import Settings
from app.database import make_engine, make_session_factory
from app.observability import install_handlers
from app.api import auth, classes, tasks, registration, faces, sessions, checkins, records
from app.upload_limits import UploadLimitMiddleware

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = make_engine(settings)
        app.state.sessions = make_session_factory(app.state.engine)
        app.state.redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            yield
        finally:
            app.state.redis.close()
            app.state.engine.dispose()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    app = FastAPI(
        title="人脸签到系统",
        version="0.1.0",
        description="本地课程人脸签到：注册录入、照片管理、匿名场次签到与受保护的记录查询。",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(UploadLimitMiddleware)
    install_handlers(app)
    app.include_router(auth.router)
    app.include_router(classes.router)
    app.include_router(tasks.router)
    app.include_router(registration.router)
    app.include_router(faces.router)
    app.include_router(sessions.router)
    app.include_router(checkins.router)
    app.include_router(records.router)

    @app.get("/api/health/ready", tags=["health"])
    def ready():
        checks = {"mysql": "unavailable", "redis": "unavailable", "model_worker": "unavailable"}
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["mysql"] = "ok"
        except Exception:
            pass
        try:
            if app.state.redis.ping():
                checks["redis"] = "ok"
                if any(app.state.redis.scan_iter('worker:model:*', count=50)):
                    checks['model_worker']='ok'
        except Exception:
            pass
        healthy=all(value=='ok' for value in checks.values())
        return JSONResponse({"status": "ready" if healthy else "not_ready", "checks": checks}, status_code=200 if healthy else 503)

    @app.get("/api/health/live", response_model=LiveResponse, tags=["health"])
    def live() -> LiveResponse:
        """仅检查 API 存活，不代表数据库或人脸模型就绪。"""
        return LiveResponse()

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get('/{page}.html', include_in_schema=False)
    def page(page: str):
        from fastapi import HTTPException
        if page not in {'register', 'login', 'faces', 'sessions', 'checkin', 'records'}:
            raise HTTPException(status_code=404)
        return FileResponse(WEB_DIR / (page + '.html'))

    # Only public assets are mounted; photos and configuration must stay private.
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    return app
