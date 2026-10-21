# Vehiculo IoT API

FastAPI wrapper around the `vehiculo_iot` MySQL schema. Exposes all stored procedures as REST endpoints and provides a WebSocket endpoint that executes and monitors "demos" (predefined command sequences) in real time.

Designed to run locally, against RDS, and eventually on EC2.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Setup](#setup)
  - [1. Clone and create a virtual environment](#1-clone-and-create-a-virtual-environment)
  - [2. Install dependencies](#2-install-dependencies)
  - [3. Configure environment variables](#3-configure-environment-variables)
  - [4. Prepare the database](#4-prepare-the-database)
  - [5. (RDS only) Download the AWS CA bundle](#5-rds-only-download-the-aws-ca-bundle)
- [Running the API](#running-the-api)
- [REST API reference](#rest-api-reference)
  - [Vehículos](#vehículos)
  - [Comandos](#comandos)
  - [Estado](#estado)
  - [Historial](#historial)
  - [Demos](#demos)
  - [Movimientos de demo](#movimientos-de-demo)
  - [Meta](#meta)
- [WebSocket: executing and monitoring demos](#websocket-executing-and-monitoring-demos)
  - [Endpoint](#endpoint)
  - [Client → Server messages](#client--server-messages)
  - [Server → Client messages](#server--client-messages)
  - [Example session](#example-session)
  - [Test from the browser console](#test-from-the-browser-console)
- [Connecting from an ESP8266](#connecting-from-an-esp8266)
- [Database schema](#database-schema)

---

## Features

- Full CRUD over vehicles, commands, states, history, demos, and demo movements — all routed through the stored procedures already defined in `vehiculo_iot`.
- Async MySQL access via `aiomysql` connection pool.
- **Real-time demo execution over WebSocket**: start, cancel, and monitor a demo sequence; multiple subscribers can watch the same demo simultaneously.
- Configurable for local MySQL, RDS with TLS, or anything in between.
- Ready for EC2 deployment behind systemd + Nginx (WebSocket-aware) or an ALB.

---

## Tech stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI |
| ASGI server | Uvicorn |
| DB driver | aiomysql (async, wraps PyMySQL) |
| Validation | Pydantic v2 + pydantic-settings |
| WebSocket | Starlette (bundled with FastAPI) |

---

## Project structure

```
vehiculo-iot-api/
├── .env                    # local secrets (not committed)
├── .env.example
├── requirements.txt
├── run.py
├── certs/
│   └── global-bundle.pem   # AWS RDS CA bundle (only for RDS)
└── app/
    ├── __init__.py
    ├── config.py           # pydantic-settings
    ├── database.py         # aiomysql pool + call_procedure helpers
    ├── schemas.py          # Pydantic models
    ├── main.py             # FastAPI app, lifespan, CORS, routers
    ├── services/
    │   ├── __init__.py
    │   └── demo_runner.py  # WebSocket demo runner + subscriber manager
    └── routers/
        ├── __init__.py
        ├── vehiculos.py
        ├── comandos.py
        ├── estado.py
        ├── historial.py
        ├── demos.py
        └── ws.py
```

---

## Requirements

- **Python 3.13** (recommended). Python 3.14 works only with updated dependency pins — see [Troubleshooting](#troubleshooting).
- MySQL 8.x (local) or Amazon RDS MySQL/Aurora.
- The `vehiculo_iot` schema and stored procedures must already exist (see `CREATE DATABASE IF NOT EXISTS vehiculo_iot.txt`).

---

## Setup

### 1. Clone and create a virtual environment

```powershell
# Windows PowerShell
cd C:\
git clone <your-repo-url> vehiculo-iot-api
cd vehiculo-iot-api
py -3.13 -m venv .venv
.venv\Scripts\Activate
```

```bash
# Linux / macOS
git clone <your-repo-url> vehiculo-iot-api
cd vehiculo-iot-api
python3.13 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt`:

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
aiomysql==0.2.0
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
websockets==13.1
```

### 3. Configure environment variables

Copy the template and fill in your values:

```bash
cp .env.example .env
```

`.env.example`:

```dotenv
# ---------- Database ----------
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=changeme
DB_NAME=vehiculo_iot

# ---------- TLS (RDS) ----------
# Set to true when connecting to RDS.
DB_SSL=false
# Path to the AWS RDS CA bundle. Only used when DB_SSL=true.
DB_SSL_CA=certs/global-bundle.pem

# ---------- CORS ----------
# "*" or a comma-separated list of origins.
ALLOWED_ORIGINS=*
```

For a local MySQL, `DB_SSL=false` is fine. For RDS, see the next section.

### 4. Prepare the database

Run the schema and seed script against your MySQL/RDS instance:

```bash
mysql -h <host> -u <user> -p < CREATE\ DATABASE\ IF\ NOT\ EXISTS\ vehiculo_iot.txt
```

This will create the schema, define all stored procedures, and seed one vehicle ("Excavadora IoT") with 9 commands and one demo containing 8 movements.

### 5. (RDS only) Download the AWS CA bundle

AWS RDS presents a certificate signed by AWS's own CA, which is not in the default trust store. Download the global bundle:

```powershell
mkdir certs
Invoke-WebRequest `
  -Uri "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem" `
  -OutFile "certs\global-bundle.pem"
```

```bash
mkdir -p certs
curl -o certs/global-bundle.pem \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

Then set in `.env`:

```dotenv
DB_SSL=true
DB_SSL_CA=certs/global-bundle.pem
```

---

## Running the API

```bash
python run.py
```

Uvicorn starts on `http://0.0.0.0:8000`. Open:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

For production (no reload, multiple workers):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

> Note: the WebSocket demo runner keeps state in memory. If you run multiple workers, a demo started on worker A won't be visible to clients connected to worker B. For a single EC2 instance, either run with `--workers 1` or add a shared state layer (Redis). See [Roadmap](#roadmap).

---

## REST API reference

Base URL: `http://localhost:8000`

All endpoints are backed by the stored procedures in the database. Errors from MySQL surface as HTTP 500 with the original error message.

### Vehículos

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/vehiculos` | `sp_obtener_vehiculos` | — |
| GET | `/vehiculos/{id_vehiculo}` | `sp_obtener_vehiculo` | — |
| POST | `/vehiculos` | `sp_crear_vehiculo` | `{nombre, modelo, descripcion, microcontrolador}` |
| PUT | `/vehiculos/{id_vehiculo}` | `sp_actualizar_vehiculo` | `{nombre, modelo, descripcion, microcontrolador, activo}` |
| DELETE | `/vehiculos/{id_vehiculo}` | `sp_eliminar_vehiculo` | — |

### Comandos

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/comandos/vehiculo/{id_vehiculo}` | `sp_obtener_comandos_vehiculo` | — |
| POST | `/comandos` | `sp_crear_comando` | `{id_vehiculo, nombre, codigo, descripcion}` |
| PUT | `/comandos/{id_comando}` | `sp_actualizar_comando` | `{nombre, codigo, descripcion, activo}` |
| DELETE | `/comandos/{id_comando}` | `sp_eliminar_comando` | — |

### Estado

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/estado/{id_vehiculo}` | `sp_obtener_estado` | — |
| POST | `/estado/actualizar` | `sp_actualizar_estado` | `{id_vehiculo, id_comando, conectado}` |

### Historial

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/historial/{id_vehiculo}` | `sp_obtener_historial` | — |
| POST | `/historial` | `sp_registrar_historial` | `{id_vehiculo, id_comando, origen}` |

### Demos

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/demos/vehiculo/{id_vehiculo}` | `sp_obtener_demos` | — |
| POST | `/demos` | `sp_crear_demo` | `{id_vehiculo, nombre, descripcion}` |
| PUT | `/demos/{id_demo}` | `sp_actualizar_demo` | `{nombre, descripcion, activo}` |
| DELETE | `/demos/{id_demo}` | `sp_eliminar_demo` | — |

### Movimientos de demo

| Method | Path | Procedure | Body / Params |
|---|---|---|---|
| GET | `/demos/{id_demo}/movimientos` | `sp_obtener_movimientos_demo` | — |
| POST | `/demos/movimientos` | `sp_agregar_movimiento_demo` | `{id_demo, id_comando, orden, duracion_ms, pausa_ms}` |
| PUT | `/demos/movimientos/{id_mov}` | `sp_actualizar_movimiento_demo` | `{id_comando, orden, duracion_ms, pausa_ms}` |
| DELETE | `/demos/movimientos/{id_mov}` | `sp_eliminar_movimiento_demo` | — |

### Meta

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status": "ok", "db": "<db_name>"}` |

---

## WebSocket: executing and monitoring demos

### Endpoint

```
ws://localhost:8000/ws/demos/{id_demo}
```

Replace `{id_demo}` with the demo you want to run or watch. Multiple clients can connect to the same `id_demo` and all receive the same broadcast.

### Client → Server messages

All messages are JSON.

| Message | Effect |
|---|---|
| `{"accion": "ejecutar"}` | Loads movements from the DB and starts the sequence |
| `{"accion": "detener"}` | Cancels the currently running sequence |
| `{"accion": "ping"}` | Keepalive; server replies with `pong` |

Anything else returns an `error` message.

### Server → Client messages

Every message is a JSON object with a `tipo` field.

| `tipo` | When | Example payload |
|---|---|---|
| `bienvenida` | Immediately on connect | `{"tipo":"bienvenida","id_demo":1,"corriendo":false}` |
| `inicio` | After `ejecutar` | `{"tipo":"inicio","id_demo":1,"total_movimientos":8}` |
| `comando` | Before each movement | `{"tipo":"comando","orden":1,"id_comando":1,"codigo":1,"nombre":"AVANZAR","duracion_ms":2000}` |
| `pausa` | Between movements (if `pausa_ms > 0`) | `{"tipo":"pausa","orden":1,"duracion_ms":400}` |
| `fin` | Sequence completed normally | `{"tipo":"fin","id_demo":1}` |
| `cancelado` | After `detener` | `{"tipo":"cancelado","id_demo":1}` |
| `error` | Bad input or DB error | `{"tipo":"error","detalle":"..."}` |
| `pong` | Reply to `ping` | `{"tipo":"pong"}` |

Field meanings for a `comando` message:

| Field | Meaning |
|---|---|
| `orden` | Position in the sequence (1, 2, 3…) |
| `id_comando` | FK to `comandos.id_comando` |
| `codigo` | The integer the firmware matches on |
| `nombre` | Human-readable command name |
| `duracion_ms` | How long to hold this action |

The server owns the timing — the client just executes each command when it arrives.

### Example session

Given the seeded demo (`Demo principal`, 8 movements), a full run looks like:

```jsonc
{"tipo":"bienvenida","id_demo":1,"corriendo":false}

// client sends: {"accion":"ejecutar"}
{"tipo":"inicio","id_demo":1,"total_movimientos":8}

{"tipo":"comando","orden":1,"id_comando":1,"codigo":1,"nombre":"AVANZAR","duracion_ms":2000}
{"tipo":"pausa","orden":1,"duracion_ms":400}

{"tipo":"comando","orden":2,"id_comando":3,"codigo":3,"nombre":"GIRAR_IZQUIERDA","duracion_ms":1000}
{"tipo":"pausa","orden":2,"duracion_ms":300}

// ... 6 more movements ...

{"tipo":"comando","orden":8,"id_comando":9,"codigo":9,"nombre":"DETENER","duracion_ms":500}

{"tipo":"fin","id_demo":1}
```

Total wall-clock time for the seeded demo is about 13 seconds.

### Test from the browser console

Open http://localhost:8000/docs (or any page served by the API), open DevTools, paste:

```js
const ws = new WebSocket("ws://localhost:8000/ws/demos/1");
ws.onmessage = e => console.log("←", JSON.parse(e.data));
ws.onopen = () => ws.send(JSON.stringify({ accion: "ejecutar" }));
// later: ws.send(JSON.stringify({ accion: "detener" }));
```

To also verify multi-subscriber broadcast, open a second tab with the same code but **without** sending `ejecutar`. It will receive every event the first tab triggered.

---

## Connecting from an ESP8266

The ESP opens a WebSocket to `/ws/demos/{id_demo}`, sends `{"accion":"ejecutar"}`, and reacts to `comando` / `pausa` / `fin` messages:

```cpp
// pseudocode
on_message(json):
    switch (json.tipo):
        case "comando":
            ejecutar_movimiento(json.codigo);
            // keep motors active for json.duracion_ms
            break;
        case "pausa":
            detener_motores();
            break;
        case "fin":
            detener_motores();
            break;
```

Because the server owns the timing and every command has a stable integer `codigo`, the firmware stays small — no state machine, no duplicated logic.

---

## Database schema

```sql
vehiculos(id_vehiculo PK, nombre, modelo, descripcion,
          microcontrolador, fecha_registro, activo)

comandos(id_comando PK, id_vehiculo FK, nombre, codigo,
         descripcion, activo)
         UNIQUE (id_vehiculo, codigo)
         UNIQUE (id_vehiculo, nombre)

estado_vehiculo(id_estado PK, id_vehiculo FK UNIQUE, id_comando FK,
                fecha_actualizacion, conectado)

historial_comandos(id_historial PK, id_vehiculo FK, id_comando FK,
                   fecha_hora, origen)

demos(id_demo PK, id_vehiculo FK, nombre, descripcion, activo)

demo_movimientos(id_demo_movimiento PK, id_demo FK, id_comando FK,
                 orden, duracion_ms, pausa_ms)
                 UNIQUE (id_demo, orden)
```

All foreign keys cascade on delete/update, except `demo_movimientos.id_comando` which is `ON DELETE RESTRICT` (a command in use by a demo cannot be deleted).

Stored procedures:

```
sp_crear_vehiculo, sp_obtener_vehiculos, sp_obtener_vehiculo,
sp_actualizar_vehiculo, sp_eliminar_vehiculo

sp_crear_comando, sp_obtener_comandos_vehiculo,
sp_actualizar_comando, sp_eliminar_comando

sp_actualizar_estado, sp_obtener_estado

sp_registrar_historial, sp_obtener_historial

sp_crear_demo, sp_obtener_demos,
sp_actualizar_demo, sp_eliminar_demo

sp_agregar_movimiento_demo, sp_obtener_movimientos_demo,
sp_actualizar_movimiento_demo, sp_eliminar_movimiento_demo
```
