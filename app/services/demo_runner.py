import asyncio
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket

from app.database import call_procedure, fetch_one


def _normalize_estado(estado: dict[str, Any] | None) -> dict[str, Any] | None:
    """Make a raw estado_vehiculo row JSON-safe."""
    if not estado:
        return None
    if isinstance(estado.get("fecha_actualizacion"), datetime):
        estado["fecha_actualizacion"] = estado["fecha_actualizacion"].isoformat()
    if "conectado" in estado:
        estado["conectado"] = bool(estado["conectado"])
    return estado


class DemoRunner:
    """Executes demo sequences and broadcasts command + vehicle-state events."""

    def __init__(self) -> None:
        self.subscribers: dict[int, set[WebSocket]] = {}
        self.demo_to_vehicle: dict[int, int] = {}
        self.last_estado: dict[int, dict[str, Any]] = {}
        self.tasks: dict[int, asyncio.Task] = {}

    # ---------- subscriptions ----------
    async def subscribe(self, id_demo: int, ws: WebSocket) -> None:
        self.subscribers.setdefault(id_demo, set()).add(ws)

    async def unsubscribe(self, id_demo: int, ws: WebSocket) -> None:
        subs = self.subscribers.get(id_demo)
        if subs:
            subs.discard(ws)
            if not subs:
                self.subscribers.pop(id_demo, None)

    async def broadcast(self, id_demo: int, message: dict[str, Any]) -> None:
        for ws in list(self.subscribers.get(id_demo, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.subscribers[id_demo].discard(ws)

    # ---------- vehicle resolution ----------
    async def resolve_vehiculo(self, id_demo: int) -> Optional[int]:
        if id_demo in self.demo_to_vehicle:
            return self.demo_to_vehicle[id_demo]
        row = await fetch_one(
            "SELECT id_vehiculo FROM demos WHERE id_demo = %s", (id_demo,)
        )
        if not row:
            return None
        self.demo_to_vehicle[id_demo] = row["id_vehiculo"]
        return row["id_vehiculo"]

    async def resolve_demos_for_vehiculo(self, id_vehiculo: int) -> list[int]:
        """Every demo id that belongs to a vehicle. Used for fan-out to WS rooms."""
        rows = await call_procedure("sp_obtener_demos", (id_vehiculo,))
        demos = rows[0] if rows else []
        return [d["id_demo"] for d in demos if d.get("activo", True)]

    # ---------- estado ----------
    async def _fetch_estado(self, id_vehiculo: int) -> dict[str, Any] | None:
        rows = await call_procedure("sp_obtener_estado", (id_vehiculo,))
        row = rows[0][0] if rows and rows[0] else None
        return _normalize_estado(row)

    async def broadcast_estado(self, id_demo: int, id_vehiculo: int) -> dict[str, Any] | None:
        """Broadcast to a single demo room. Used inside the demo runner."""
        estado = await self._fetch_estado(id_vehiculo)
        if estado is not None:
            self.last_estado[id_vehiculo] = estado
        await self.broadcast(id_demo, {"tipo": "estado", "estado": estado})
        return estado

    async def broadcast_estado_to_vehiculo(
        self, id_vehiculo: int
    ) -> dict[str, Any] | None:
        """Broadcast to every demo room of a vehicle. Used for manual commands
        so any client watching any demo of this vehicle sees the change."""
        estado = await self._fetch_estado(id_vehiculo)
        if estado is not None:
            self.last_estado[id_vehiculo] = estado

        message = {"tipo": "estado", "estado": estado}
        demos = await self.resolve_demos_for_vehiculo(id_vehiculo)
        for id_demo in demos:
            await self.broadcast(id_demo, message)
        return estado

    async def get_snapshot(self, id_demo: int) -> dict[str, Any]:
        id_vehiculo = await self.resolve_vehiculo(id_demo)
        if id_vehiculo is None:
            return {"corriendo": self.is_running(id_demo), "estado": None}
        estado = self.last_estado.get(id_vehiculo)
        if estado is None:
            estado = await self._fetch_estado(id_vehiculo)
            if estado is not None:
                self.last_estado[id_vehiculo] = estado
        return {"corriendo": self.is_running(id_demo), "estado": estado}

    # ---------- execution ----------
    async def _run(
        self, id_demo: int, id_vehiculo: int, movimientos: list[dict]
    ) -> None:
        try:
            await self.broadcast(id_demo, {
                "tipo": "inicio",
                "id_demo": id_demo,
                "id_vehiculo": id_vehiculo,
                "total_movimientos": len(movimientos),
            })

            for mov in movimientos:
                await call_procedure(
                    "sp_actualizar_estado",
                    (id_vehiculo, mov["id_comando"], True),
                )

                await self.broadcast(id_demo, {
                    "tipo": "comando",
                    "id_demo": id_demo,
                    "orden": mov["orden"],
                    "id_comando": mov["id_comando"],
                    "codigo": mov["codigo"],
                    "nombre": mov["comando"],
                    "duracion_ms": mov["duracion_ms"],
                })

                # Per-demo broadcast (unchanged from current behavior)
                await self.broadcast_estado(id_demo, id_vehiculo)

                await asyncio.sleep(mov["duracion_ms"] / 1000)

                if mov.get("pausa_ms"):
                    await self.broadcast(id_demo, {
                        "tipo": "pausa",
                        "id_demo": id_demo,
                        "orden": mov["orden"],
                        "duracion_ms": mov["pausa_ms"],
                    })
                    await asyncio.sleep(mov["pausa_ms"] / 1000)

            await self.broadcast(id_demo, {"tipo": "fin", "id_demo": id_demo})

        except asyncio.CancelledError:
            await self.broadcast(id_demo, {"tipo": "cancelado", "id_demo": id_demo})
            raise
        finally:
            self.tasks.pop(id_demo, None)

    def start(self, id_demo: int, id_vehiculo: int, movimientos: list[dict]) -> None:
        if id_demo in self.tasks:
            self.tasks[id_demo].cancel()
        task = asyncio.create_task(self._run(id_demo, id_vehiculo, movimientos))
        self.tasks[id_demo] = task

    def stop(self, id_demo: int) -> bool:
        task = self.tasks.get(id_demo)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, id_demo: int) -> bool:
        t = self.tasks.get(id_demo)
        return bool(t and not t.done())

    # ---------- manual state push (from WS) ----------
    async def push_manual_estado(
        self,
        id_demo: int,
        id_vehiculo: int,
        id_comando: Optional[int],
        conectado: bool,
    ) -> None:
        await call_procedure(
            "sp_actualizar_estado", (id_vehiculo, id_comando, conectado)
        )
        await self.broadcast_estado(id_demo, id_vehiculo)


runner = DemoRunner()