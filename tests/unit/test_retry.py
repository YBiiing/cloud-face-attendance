import pytest
from sqlalchemy.exc import OperationalError
from app.services.retry import retry_transaction


def test_deadlock_bounded_retry_and_other_errors(monkeypatch):
    monkeypatch.setattr('app.services.retry.time.sleep',lambda _:None)
    attempts=[]
    @retry_transaction
    def operation(code):
        attempts.append(code)
        raise OperationalError('test',{},Exception(code,'test-only'))
    with pytest.raises(OperationalError):operation(1213)
    assert len(attempts)==3
    attempts.clear()
    with pytest.raises(OperationalError):operation(2006)
    assert len(attempts)==1
