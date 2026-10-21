from fastapi import APIRouter
from app.database import call_procedure
from app.schemas import EstadoUpdate, EstadoOut

router = APIRouter(prefix="/estado", tags=["Estado"])


@router.get("/{id_vehiculo}", response_model=EstadoOut)
async def obtener(id_vehiculo: int):
    rows = await call_procedure("sp_obtener_estado", (id_vehiculo,))
    return rows[0][0] if rows and rows[0] else {}


@router.post("/actualizar")
async def actualizar(body: EstadoUpdate):
    await call_procedure(
        "sp_actualizar_estado",
        (body.id_vehiculo, body.id_comando, body.conectado),
    )
    return {"ok": True}