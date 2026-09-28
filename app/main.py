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
        description="当前仅实现页面与存活检查。业务接口按开发计划逐步接入。",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_handlers(app)

    @app.get("/api/health/ready", tags=["health"])
    def ready():
        checks = {"mysql": "unavailable", "redis": "unavailable", "model_worker": "not_configured"}
        try:
            with app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["mysql"] = "ok"
        except Exception:
            pass
        try:
            if app.state.redis.ping():
                checks["redis"] = "ok"
        except Exception:
            pass
        # Recognition readiness becomes available when the worker is implemented.
        return JSONResponse({"status": "not_ready", "checks": checks}, status_code=503)

    @app.get("/api/health/live", response_model=LiveResponse, tags=["health"])
    def live() -> LiveResponse:
        """仅检查 API 存活，不代表数据库或人脸模型就绪。"""
        return LiveResponse()

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    # Only public assets are mounted; photos and configuration must stay private.
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    return app
