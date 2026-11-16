"""학교 조회 결과를 짧게 보관해 같은 요청이 몰려도 한 번만 호출한다."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class CacheBackend(Protocol):
    def get(self, name: str) -> Awaitable[bytes | str | None]: ...

    def set(self, name: str, value: str, ex: int) -> Awaitable[object]: ...


class LiveCache:
    """Redis에 실패해도 학교 조회는 계속한다."""

    def __init__(self, backend: CacheBackend, prefix: str, ttl_seconds: int) -> None:
        self._backend = backend
        self._prefix = prefix
        self._ttl = ttl_seconds
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_load(
        self, key: str, model: type[ModelT], load: Callable[[], Awaitable[ModelT]]
    ) -> ModelT:
        name = f"{self._prefix}:live:{key}"
        cached = await self._read(name, model)
        if cached is not None:
            return cached
        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            cached = await self._read(name, model)
            if cached is not None:
                return cached
            value = await load()
            await self._write(name, value)
            return value

    async def _read(self, name: str, model: type[ModelT]) -> ModelT | None:
        try:
            raw = await self._backend.get(name)
        except (RedisError, OSError) as error:
            logger.warning("cache read failed: %s", type(error).__name__)
            return None
        if raw is None:
            return None
        try:
            return model.model_validate_json(raw)
        except ValidationError:
            logger.warning("cache value invalid, reloading: %s", name)
            return None

    async def _write(self, name: str, value: BaseModel) -> None:
        try:
            await self._backend.set(
                name, value.model_dump_json(by_alias=True), ex=self._ttl
            )
        except (RedisError, OSError) as error:
            logger.warning("cache write failed: %s", type(error).__name__)
