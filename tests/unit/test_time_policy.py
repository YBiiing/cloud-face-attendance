from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from app.services.time_policy import eligible_time,session_status


def test_boundaries_and_early_close():
    start=datetime(2026,9,28,23,59,tzinfo=timezone.utc)
    end=start+timedelta(minutes=5)
    row=SimpleNamespace(starts_at=start,ends_at=end,closed_at=None)
    assert session_status(row,start-timedelta(microseconds=1))=='SCHEDULED'
    assert eligible_time(row,start)
    assert eligible_time(row,end-timedelta(microseconds=1))
    assert not eligible_time(row,end)
    assert session_status(row,end)=='CLOSED'
    row.closed_at=start+timedelta(seconds=10)
    assert not eligible_time(row,row.closed_at)
    assert eligible_time(row,row.closed_at-timedelta(microseconds=1))
    row.closed_at=start-timedelta(seconds=1)
    assert session_status(row,start)=='CLOSED'
