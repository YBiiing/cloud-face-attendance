"""应用入口：python -m uvicorn app.main:create_app --factory。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas.health import LiveResponse
from app.config import Settings

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(
        title="人脸签到系统",
        version="0.1.0",
        description="当前仅实现页面与存活检查。业务接口按开发计划逐步接入。",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings

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
