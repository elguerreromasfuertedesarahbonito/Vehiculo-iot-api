from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import call_procedure
from app.services.demo_runner import runner

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/demos/{id_demo}")
async def ws_demo(websocket: WebSocket, id_demo: int):
    """
    Client → Server:
      {"accion": "ejecutar"}                                    start demo
      {"accion": "detener"}                                     cancel demo
      {"accion": "estado", "id_comando": 5, "conectado": true}  report vehicle state
      {"accion": "ping"}                                        keepalive

    Server → Client:
      {"tipo": "bienvenida", ..., "corriendo": bool, "estado": {...}}
      {"tipo": "inicio" | "comando" | "pausa" | "fin" | "cancelado", ...}
      {"tipo": "estado", "estado": {...}}
      {"tipo": "error" | "pong", ...}
    """
    await websocket.accept()
    await runner.subscribe(id_demo, websocket)

    id_vehiculo = await runner.resolve_vehiculo(id_demo)
    snapshot = await runner.get_snapshot(id_demo)

    await websocket.send_json({
        "tipo": "bienvenida",
        "id_demo": id_demo,
        "id_vehiculo": id_vehiculo,
        "corriendo": snapshot["corriendo"],
        "estado": snapshot["estado"],
    })

    try:
        while True:
            msg = await websocket.receive_json()
            accion = (msg or {}).get("accion")

            if accion == "ejecutar":
                if id_vehiculo is None:
                    await websocket.send_json({
                        "tipo": "error",
                        "detalle": f"Demo {id_demo} no existe",
                    })
                    continue
                rows = await call_procedure(
                    "sp_obtener_movimientos_demo", (id_demo,)
                )
                movimientos = rows[0] if rows else []
                if not movimientos:
                    await websocket.send_json({
                        "tipo": "error",
                        "detalle": "La demo no tiene movimientos registrados",
                    })
                    continue
                runner.start(id_demo, id_vehiculo, movimientos)

            elif accion == "detener":
                runner.stop(id_demo)

            elif accion == "estado":
                if id_vehiculo is None:
                    await websocket.send_json({
                        "tipo": "error",
                        "detalle": "No se pudo resolver el vehículo de esta demo",
                    })
                    continue
                id_comando = (msg or {}).get("id_comando")
                conectado = bool((msg or {}).get("conectado", False))
                await runner.push_manual_estado(
                    id_demo, id_vehiculo, id_comando, conectado
                )

            elif accion == "ping":
                await websocket.send_json({"tipo": "pong"})

            else:
                await websocket.send_json({
                    "tipo": "error",
                    "detalle": f"Acción desconocida: {accion}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"tipo": "error", "detalle": str(e)})
        except Exception:
            pass
    finally:
        await runner.unsubscribe(id_demo, websocket)