from fastapi import APIRouter
from app.database import call_procedure
from app.schemas import HistorialCreate

router = APIRouter(prefix="/historial", tags=["Historial"])


@router.get("/{id_vehiculo}")
async def obtener(id_vehiculo: int):
    rows = await call_procedure("sp_obtener_historial", (id_vehiculo,))
    return rows[0] if rows else []


@router.post("", status_code=201)
async def registrar(body: HistorialCreate):
    await call_procedure(
        "sp_registrar_historial",
        (body.id_vehiculo, body.id_comando, body.origen),
    )
    return {"ok": True}