"""One time budget shared by HTTP workflow steps and provider retries."""
import time
from contextvars import ContextVar

expires = ContextVar('request_deadline', default=None)


class DeadlineExceeded(Exception):
    pass


def remaining(limit):
    deadline = expires.get()
    budget = min(limit, deadline - time.monotonic()) if deadline is not None else limit
    if budget < 1:
        raise DeadlineExceeded('Time limit reached. Saved steps are retained; retry to continue.')
    return budget
