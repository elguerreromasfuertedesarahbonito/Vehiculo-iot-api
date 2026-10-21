import asyncio
from typing import Any
from fastapi import WebSocket


def demo_channel(id_demo: int) -> str:
    return f"demo:{id_demo}"


def vehiculo_channel(id_vehiculo: int) -> str:
    return f"vehiculo:{id_vehiculo}"


class Broadcaster:
    """In-memory pub/sub broker with optional snapshot per channel."""

    def __init__(self) -> None:
        self._subs: dict[str, set[WebSocket]] = {}
        self._last: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str, ws: WebSocket) -> dict[str, Any] | None:
        async with self._lock:
            self._subs.setdefault(channel, set()).add(ws)
            return self._last.get(channel)

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._subs.get(channel)
            if subs:
                subs.discard(ws)
                if not subs:
                    self._subs.pop(channel, None)

    async def publish(
        self,
        channel: str,
        message: dict[str, Any],
        *,
        snapshot: bool = False,
    ) -> None:
        async with self._lock:
            if snapshot:
                self._last[channel] = message
            targets = list(self._subs.get(channel, set()))

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                await self.unsubscribe(channel, ws)

    def get_snapshot(self, channel: str) -> dict[str, Any] | None:
        return self._last.get(channel)


broadcaster = Broadcaster()