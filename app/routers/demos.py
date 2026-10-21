from fastapi import APIRouter
from app.database import call_procedure
from app.schemas import DemoCreate, DemoUpdate, MovimientoCreate, MovimientoUpdate

router = APIRouter(prefix="/demos", tags=["Demos"])


# ----- Demos CRUD -----
@router.get("/vehiculo/{id_vehiculo}")
async def listar(id_vehiculo: int):
    rows = await call_procedure("sp_obtener_demos", (id_vehiculo,))
    return rows[0] if rows else []


@router.post("", status_code=201)
async def crear(body: DemoCreate):
    rows = await call_procedure(
        "sp_crear_demo", (body.id_vehiculo, body.nombre, body.descripcion)
    )
    return rows[0][0] if rows and rows[0] else {"ok": True}


@router.put("/{id_demo}")
async def actualizar(id_demo: int, body: DemoUpdate):
    await call_procedure(
        "sp_actualizar_demo",
        (id_demo, body.nombre, body.descripcion, body.activo),
    )
    return {"ok": True}


@router.delete("/{id_demo}")
async def eliminar(id_demo: int):
    await call_procedure("sp_eliminar_demo", (id_demo,))
    return {"ok": True}


# ----- Movimientos -----
@router.get("/{id_demo}/movimientos")
async def listar_movimientos(id_demo: int):
    rows = await call_procedure("sp_obtener_movimientos_demo", (id_demo,))
    return rows[0] if rows else []


@router.post("/movimientos", status_code=201)
async def agregar_movimiento(body: MovimientoCreate):
    await call_procedure(
        "sp_agregar_movimiento_demo",
        (body.id_demo, body.id_comando, body.orden, body.duracion_ms, body.pausa_ms),
    )
    return {"ok": True}


@router.put("/movimientos/{id_mov}")
async def actualizar_movimiento(id_mov: int, body: MovimientoUpdate):
    await call_procedure(
        "sp_actualizar_movimiento_demo",
        (id_mov, body.id_comando, body.orden, body.duracion_ms, body.pausa_ms),
    )
    return {"ok": True}


@router.delete("/movimientos/{id_mov}")
async def eliminar_movimiento(id_mov: int):
    await call_procedure("sp_eliminar_movimiento_demo", (id_mov,))
    return {"ok": True}