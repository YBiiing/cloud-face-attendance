"""Retry only known MySQL transaction conflicts, with a fresh transaction."""
from functools import wraps
import time
from sqlalchemy.exc import OperationalError


def retry_transaction(function):
    @wraps(function)
    def execute(*args, **kwargs):
        for attempt in range(3):
            try:
                return function(*args, **kwargs)
            except OperationalError as error:
                code = error.orig.args[0] if getattr(error.orig, 'args', ()) else None
                if code not in {1205, 1213} or attempt == 2:
                    raise
                time.sleep(.02 * (2 ** attempt))
    return execute
