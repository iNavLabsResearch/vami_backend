from collections.abc import Callable
from functools import lru_cache, wraps
from time import time
from typing import Any, ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")


class TTLCache:
    """Simple in-memory TTL cache for hot paths (static memory cache)."""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 1024) -> None:
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._store: dict[tuple[Any, ...], tuple[float, Any]] = {}

    def get(self, key: tuple[Any, ...]) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        created_at, value = item
        if time() - created_at > self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: tuple[Any, ...], value: Any) -> None:
        if len(self._store) >= self.max_size:
            # naive eviction: clear all
            self._store.clear()
        self._store[key] = (time(), value)


def ttl_cached(ttl_seconds: int = 60, max_size: int = 1024) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to cache pure functions in memory for a short TTL."""

    cache = TTLCache(ttl_seconds=ttl_seconds, max_size=max_size)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = (*args, *sorted(kwargs.items()))
            cached = cache.get(key)
            if cached is not None:
                return cached  # type: ignore[return-value]
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        return wrapper

    return decorator


__all__ = ["TTLCache", "ttl_cached", "lru_cache"]

