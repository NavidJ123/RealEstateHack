"""Caching utilities used across services."""

from __future__ import annotations

import functools
import threading
from typing import Callable, Dict, Tuple, TypeVar

T = TypeVar("T")

_cache_lock = threading.Lock()
_memory_cache: Dict[Tuple[str, Tuple], T] = {}


def memoize(prefix: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Lightweight thread-safe memoization decorator.

    We allow callers to provide a prefix so cached keys are grouped by logical
    concern, which keeps cache inspection and invalidation straightforward.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (prefix, args, tuple(sorted(kwargs.items())))
            with _cache_lock:
                if key in _memory_cache:
                    return _memory_cache[key]
            result = func(*args, **kwargs)
            with _cache_lock:
                _memory_cache[key] = result
            return result

        return wrapper

    return decorator


def clear_prefix(prefix: str) -> None:
    """Clear all cache entries for the given prefix."""

    with _cache_lock:
        to_delete = [key for key in _memory_cache if key[0] == prefix]
        for key in to_delete:
            del _memory_cache[key]


__all__ = ["memoize", "clear_prefix"]

