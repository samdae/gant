"""Runtime context for schedule-scoped logging."""

from contextvars import ContextVar, Token
from typing import Callable, Optional, Tuple


_current_schedule_id: ContextVar[Optional[int]] = ContextVar(
    "current_schedule_id", default=None
)
_error_logger: ContextVar[Optional[Callable[[int, str, str, Optional[str]], None]]] = (
    ContextVar("schedule_error_logger", default=None)
)


def set_schedule_context(
    schedule_id: int,
    error_logger: Callable[[int, str, str, Optional[str]], None],
) -> Tuple[Token, Token]:
    token_id: Token = _current_schedule_id.set(schedule_id)
    token_logger: Token = _error_logger.set(error_logger)
    return token_id, token_logger


def reset_schedule_context(tokens: Tuple[Token, Token]) -> None:
    token_id, token_logger = tokens
    _current_schedule_id.reset(token_id)
    _error_logger.reset(token_logger)


def log_schedule_error(
    error_type: str, error_message: str, error_detail: Optional[str] = None
) -> None:
    schedule_id = _current_schedule_id.get()
    error_logger = _error_logger.get()
    if schedule_id is None or error_logger is None:
        return
    try:
        error_logger(schedule_id, error_type, error_message, error_detail)
    except Exception:
        pass
