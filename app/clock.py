from datetime import datetime, timezone


def utc_now() -> datetime:
    """Single injectable clock used by business services."""
    return datetime.now(timezone.utc)
