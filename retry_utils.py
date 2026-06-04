#!/usr/bin/env python3
"""Shared async retry decorator with exponential backoff for network operations."""

import asyncio
import functools
import random
import logging
from typing import Callable, Any, Optional, Tuple, Type

# Keywords used to recognize a network-related error from its message
NETWORK_KEYWORDS = (
    'connection', 'timeout', 'network', 'websocket', 'client', 'server'
)


def async_retry(max_attempts: int = 3, base_delay: float = 0.5, max_delay: float = 5.0,
                *,
                retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
                retry_on_message: bool = False,
                logger: Optional[logging.Logger] = None,
                verbose_attr: Optional[str] = None):
    """
    Decorator for async network operations with exponential backoff retry logic.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 0.5)
        max_delay: Maximum delay in seconds between retries (default: 5.0)
        retry_exceptions: Exception types that trigger a retry. Exceptions outside
            this tuple propagate immediately.
        retry_on_message: If True, only retry when the exception message contains a
            network keyword (NETWORK_KEYWORDS); otherwise retry any caught exception.
        logger: Optional logger; retry attempts are logged at debug level.
        verbose_attr: Optional attribute name on the first positional arg (e.g. 'self').
            If that attribute is truthy, retry attempts are printed to stdout.

    Returns:
        Decorated coroutine function with retry logic.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_exception = e

                    # Decide whether this error is worth retrying
                    retryable = True
                    if retry_on_message:
                        retryable = any(kw in str(e).lower() for kw in NETWORK_KEYWORDS)

                    # Don't retry on the last attempt or for non-retryable errors
                    if attempt == max_attempts - 1 or not retryable:
                        break

                    # Exponential backoff with jitter to avoid thundering herd
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    total_delay = delay + random.uniform(0, 0.1 * delay)

                    msg = f"Network error on attempt {attempt + 1}/{max_attempts}, retrying in {total_delay:.2f}s: {e}"
                    if logger:
                        logger.debug(msg)
                    elif verbose_attr and args and getattr(args[0], verbose_attr, False):
                        print(f"🔄 {msg}")

                    await asyncio.sleep(total_delay)

            # All retry attempts failed
            raise last_exception

        return wrapper
    return decorator
