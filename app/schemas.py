from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# ---------- Vehículos ----------
class VehiculoCreate(BaseModel):
    nombre: str = Field(..., max_length=80)
    modelo: Optional[str] = Field(None, max_length=80)
    descripcion: Optional[str] = Field(None, max_length=255)
    microcontrolador: Optional[str] = Field(None, max_length=50)


class VehiculoUpdate(BaseModel):
    nombre: str
    modelo: Optional[str] = None
    descripcion: Optional[str] = None
    microcontrolador: Optional[str] = None
    activo: bool = True


class VehiculoOut(BaseModel):
    id_vehiculo: int
    nombre: str
    modelo: Optional[str]
    descripcion: Optional[str]
    microcontrolador: Optional[str]
    fecha_registro: datetime
    activo: bool


class ComandoManualCreate(BaseModel):
    """Payload for POST /vehiculos/{id_vehiculo}/comando-manual.
    `origen` is stored in historial_comandos.origen and defaults to MANUAL."""
    id_comando: int
    origen: str = Field("MANUAL", max_length=30)


# ---------- Comandos ----------
class ComandoCreate(BaseModel):
    id_vehiculo: int
    nombre: str = Field(..., max_length=60)
    codigo: int
    descripcion: Optional[str] = None


class ComandoUpdate(BaseModel):
    nombre: str
    codigo: int
    descripcion: Optional[str] = None
    activo: bool = True


class ComandoOut(BaseModel):
    id_comando: int
    id_vehiculo: int
    nombre: str
    codigo: int
    descripcion: Optional[str]
    activo: bool


# ---------- Estado ----------
class EstadoUpdate(BaseModel):
    id_vehiculo: int
    id_comando: Optional[int] = None
    conectado: bool = False


class EstadoOut(BaseModel):
    id_vehiculo: int
    vehiculo: str
    id_comando: Optional[int]
    comando: Optional[str]
    codigo: Optional[int]
    conectado: bool
    fecha_actualizacion: datetime


# ---------- Historial ----------
class HistorialCreate(BaseModel):
    id_vehiculo: int
    id_comando: Optional[int] = None
    origen: str = "MANUAL"


# ---------- Demos ----------
class DemoCreate(BaseModel):
    id_vehiculo: int
    nombre: str
    descripcion: Optional[str] = None


class DemoUpdate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True


class MovimientoCreate(BaseModel):
    id_demo: int
    id_comando: int
    orden: int
    duracion_ms: int
    pausa_ms: int = 0


class MovimientoUpdate(BaseModel):
    id_comando: int
    orden: int
    duracion_ms: int
    pausa_ms: int = 0