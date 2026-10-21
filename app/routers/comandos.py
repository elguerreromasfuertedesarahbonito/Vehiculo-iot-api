from fastapi import APIRouter
from app.database import call_procedure
from app.schemas import ComandoCreate, ComandoUpdate, ComandoOut

router = APIRouter(prefix="/comandos", tags=["Comandos"])


@router.get("/vehiculo/{id_vehiculo}", response_model=list[ComandoOut])
async def listar_por_vehiculo(id_vehiculo: int):
    rows = await call_procedure("sp_obtener_comandos_vehiculo", (id_vehiculo,))
    return rows[0] if rows else []


@router.post("", status_code=201)
async def crear(body: ComandoCreate):
    rows = await call_procedure(
        "sp_crear_comando",
        (body.id_vehiculo, body.nombre, body.codigo, body.descripcion),
    )
    return rows[0][0] if rows and rows[0] else {"ok": True}


@router.put("/{id_comando}")
async def actualizar(id_comando: int, body: ComandoUpdate):
    await call_procedure(
        "sp_actualizar_comando",
        (id_comando, body.nombre, body.codigo, body.descripcion, body.activo),
    )
    return {"ok": True}


@router.delete("/{id_comando}")
async def eliminar(id_comando: int):
    await call_procedure("sp_eliminar_comando", (id_comando,))
    return {"ok": True}