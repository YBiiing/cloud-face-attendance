"""Explicit environment configuration; never include secret values in errors."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str = field(repr=False)
    app_secret: str = field(repr=False)
    redis_url: str = field(repr=False)
    storage_dir: Path
    model_dir: Path
    cookie_secure: bool

    @classmethod
    def from_env(cls) -> "Settings":
        required = ["APP_ENV", "MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "APP_SECRET", "REDIS_URL"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError("Missing configuration: " + ", ".join(missing))
        environment = os.environ["APP_ENV"]
        if environment not in {"local", "test", "production"}:
            raise RuntimeError("Invalid APP_ENV")
        secure = os.getenv("COOKIE_SECURE", "true").lower()
        if secure not in {"true", "false"}:
            raise RuntimeError("Invalid COOKIE_SECURE")
        if environment == "production" and secure != "true":
            raise RuntimeError("Production requires COOKIE_SECURE=true")
        if len(os.environ["APP_SECRET"]) < 32:
            raise RuntimeError("APP_SECRET must contain at least 32 characters")
        try:
            port = int(os.getenv("MYSQL_PORT", "3306"))
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            raise RuntimeError("Invalid MYSQL_PORT") from None
        return cls(environment, os.environ["MYSQL_HOST"], port,
                   os.environ["MYSQL_DATABASE"], os.environ["MYSQL_USER"],
                   os.environ["MYSQL_PASSWORD"], os.environ["APP_SECRET"],
                   os.environ["REDIS_URL"], Path(os.getenv("STORAGE_DIR", "storage")),
                   Path(os.getenv("MODEL_DIR", "models")), secure == "true")
