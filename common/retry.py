"""Resilience utilities: retry with exponential backoff and safe execution."""

import time
from typing import Any, Callable, Optional, Tuple, Type

def with_retry(
    action: Callable[[], Any],
    max_attempts: int = 3,
    initial_delay_sec: float = 0.2,
    backoff_factor: float = 2.0,
    allowed_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Any:
    """Executes a callable with retries upon specified exceptions."""
    delay = initial_delay_sec
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return action()
        except allowed_exceptions as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            if on_retry:
                on_retry(attempt, exc)
            time.sleep(delay)
            delay *= backoff_factor

    if last_error:
        raise last_error
