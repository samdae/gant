"""Runtime context for schedule-scoped logging."""

from contextlib import contextmanager
from datetime import date
from contextvars import ContextVar, Token
from typing import Callable, Optional, Tuple


_current_schedule_job_id: ContextVar[Optional[int]] = ContextVar(
    "current_schedule_job_id", default=None
)
_error_logger: ContextVar[Optional[Callable[[int, str, str, Optional[str]], None]]] = (
    ContextVar("schedule_error_logger", default=None)
)


def set_schedule_context(
    schedule_job_id: int,
    _unused: Optional[int],
    error_logger: Callable[[int, str, str, Optional[str]], None],
) -> Tuple[Token, Token]:
    token_job: Token = _current_schedule_job_id.set(schedule_job_id)
    token_logger: Token = _error_logger.set(error_logger)
    return token_job, token_logger


def reset_schedule_context(tokens: Tuple[Token, ...]) -> None:
    for token in tokens:
        try:
            token.var.reset(token)
        except Exception:
            pass


def get_current_schedule_id() -> Optional[int]:
    """Backward-compatible alias for get_current_schedule_job_id."""
    return _current_schedule_job_id.get()


def get_current_schedule_job_id() -> Optional[int]:
    return _current_schedule_job_id.get()


def log_schedule_error(
    error_type: str, error_message: str, error_detail: Optional[str] = None
) -> None:
    job_id = _current_schedule_job_id.get()
    error_logger = _error_logger.get()
    if job_id is None or error_logger is None:
        return
    try:
        error_logger(job_id, error_type, error_message, error_detail)
    except Exception:
        pass

_analysis_date: ContextVar[Optional[date]] = ContextVar("analysis_date", default=None)


@contextmanager
def analysis_date_scope(trade_date: str):
    token = _analysis_date.set(date.fromisoformat(trade_date))
    try:
        yield
    finally:
        _analysis_date.reset(token)


def bounded_analysis_date(requested: Optional[str] = None) -> Optional[str]:
    cutoff = _analysis_date.get()
    if cutoff is None:
        return requested
    return min(date.fromisoformat(requested), cutoff).isoformat() if requested else cutoff.isoformat()
