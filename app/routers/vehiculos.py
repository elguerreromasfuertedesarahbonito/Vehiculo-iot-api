from fastapi import APIRouter, HTTPException

from app.database import call_procedure, fetch_one
from app.schemas import (
    ComandoManualCreate,
    VehiculoCreate,
    VehiculoUpdate,
    VehiculoOut,
)
from app.services.demo_runner import runner

router = APIRouter(prefix="/vehiculos", tags=["Vehiculos"])


@router.get("", response_model=list[VehiculoOut])
async def listar():
    rows = await call_procedure("sp_obtener_vehiculos")
    return rows[0] if rows else []


@router.get("/{id_vehiculo}", response_model=VehiculoOut)
async def obtener(id_vehiculo: int):
    rows = await call_procedure("sp_obtener_vehiculo", (id_vehiculo,))
    if not rows or not rows[0]:
        raise HTTPException(404, "Vehículo no encontrado")
    return rows[0][0]


@router.post("", status_code=201)
async def crear(body: VehiculoCreate):
    rows = await call_procedure(
        "sp_crear_vehiculo",
        (body.nombre, body.modelo, body.descripcion, body.microcontrolador),
    )
    return rows[0][0] if rows and rows[0] else {"ok": True}


@router.put("/{id_vehiculo}")
async def actualizar(id_vehiculo: int, body: VehiculoUpdate):
    await call_procedure(
        "sp_actualizar_vehiculo",
        (id_vehiculo, body.nombre, body.modelo, body.descripcion,
         body.microcontrolador, body.activo),
    )
    return {"ok": True}


@router.delete("/{id_vehiculo}")
async def eliminar(id_vehiculo: int):
    await call_procedure("sp_eliminar_vehiculo", (id_vehiculo,))
    return {"ok": True}


@router.post("/{id_vehiculo}/comando-manual", status_code=201)
async def comando_manual(id_vehiculo: int, body: ComandoManualCreate):
    """
    Ejecuta un comando manual sobre un vehículo.

    Hace tres cosas en una sola llamada:
      1. Actualiza estado_vehiculo con el nuevo comando y conectado=TRUE
      2. Registra el movimiento en historial_comandos con origen=MANUAL
      3. Difunde el nuevo estado a todos los WebSockets suscritos
         a cualquier demo de este vehículo

    Los movimientos manuales quedan visibles tanto en GET /historial/{id}
    como en la conexión WS /ws/demos/{id_demo}.
    """
    # 1. Validar que el comando existe y pertenece a este vehículo
    cmd = await fetch_one(
        "SELECT id_comando, nombre, codigo, activo "
        "FROM comandos WHERE id_comando = %s AND id_vehiculo = %s",
        (body.id_comando, id_vehiculo),
    )
    if not cmd:
        raise HTTPException(
            400,
            f"El comando {body.id_comando} no existe o no pertenece al vehículo {id_vehiculo}",
        )
    if not cmd["activo"]:
        raise HTTPException(400, f"El comando '{cmd['nombre']}' está inactivo")

    # 2. Actualizar estado_vehiculo
    await call_procedure(
        "sp_actualizar_estado", (id_vehiculo, body.id_comando, True)
    )

    # 3. Registrar en historial con origen MANUAL (u override)
    await call_procedure(
        "sp_registrar_historial", (id_vehiculo, body.id_comando, body.origen)
    )

    # 4. Difundir el nuevo estado a todos los WS del vehículo
    estado = await runner.broadcast_estado_to_vehiculo(id_vehiculo)

    return {
        "ok": True,
        "id_vehiculo": id_vehiculo,
        "id_comando": body.id_comando,
        "codigo": cmd["codigo"],
        "nombre": cmd["nombre"],
        "origen": body.origen,
        "estado": estado,
    }