"""Rutas de apoyo del Hito 3: usuarios, memoria, bitácora, ajustes y borrado de datos de trabajo."""

from __future__ import annotations

import json
import sqlite3
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent import bitacora
from agent.llm import ConfigLLM
from agent.memory import memoria
from api.cotizaciones import _ultima
from api.deps import ADMINISTRADOR, QUIEN_APRUEBA, TODOS, VENDEDOR, conexion, requiere_rol, usuario_actual

router = APIRouter(prefix="/api", tags=["panel"])
Conexion = Annotated[sqlite3.Connection, Depends(conexion)]
Usuario = Annotated[dict, Depends(usuario_actual)]
RESULTADOS = Path(__file__).resolve().parents[1] / "eval" / "resultados"


# --------------------------------------------------------------------------- usuarios
@router.get("/usuarios")
def usuarios(conn: Conexion) -> list[dict]:
    """Usuarios de prueba para el selector de la interfaz (no requiere identidad: es lo que permite elegirla)."""
    return [dict(f) for f in conn.execute("SELECT id, nombre, rol FROM usuarios ORDER BY id")]


# --------------------------------------------------------------------------- memoria
class HechoNuevo(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)
    origen: str | None = Field(default=None, max_length=300)


class HechoEdicion(BaseModel):
    texto: str | None = Field(default=None, max_length=1000)
    estado: Literal["Activa", "Pausada"] | None = None


def _hecho(h: dict) -> dict:
    return {"id": str(h["id"]), "texto": h["texto"], "origen": h["origen"], "fecha": h["fecha"][:10], "estado": h["estado"],
            "por_confirmar": bool(h["por_confirmar"])}


def _con_error_de_memoria(fn):
    try:
        return fn()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/memoria")
def listar_memoria(_: Usuario, conn: Conexion) -> list[dict]:
    return [_hecho(h) for h in memoria.listar(conn)]


@router.post("/memoria", status_code=201)
def proponer_hecho(cuerpo: HechoNuevo, usuario: Annotated[dict, Depends(requiere_rol(*TODOS, accion="proponer hechos"))], conn: Conexion) -> dict:
    """Cualquier rol puede proponer un hecho; entra «por confirmar» y el agente no lo usa hasta que lo confirme quien aprueba."""
    origen = cuerpo.origen or f"Propuesto por {usuario['nombre']}"
    nuevo = _con_error_de_memoria(lambda: memoria.agregar(conn, cuerpo.texto, origen, confirmado=False))
    return _hecho(next(h for h in memoria.listar(conn) if h["id"] == nuevo))


@router.patch("/memoria/{hecho_id}")
def editar_hecho(hecho_id: int, cuerpo: HechoEdicion, _: Annotated[dict, Depends(requiere_rol(*QUIEN_APRUEBA, accion="editar la memoria"))], conn: Conexion) -> dict:
    if cuerpo.texto is None and cuerpo.estado is None:
        raise HTTPException(status_code=422, detail="Indica el texto o el estado nuevo.")
    if cuerpo.texto is not None:
        _con_error_de_memoria(lambda: memoria.editar(conn, hecho_id, cuerpo.texto))
    if cuerpo.estado is not None:
        _con_error_de_memoria(lambda: memoria.cambiar_estado(conn, hecho_id, cuerpo.estado))
    return _hecho(next(h for h in memoria.listar(conn) if h["id"] == hecho_id))


@router.post("/memoria/{hecho_id}/confirmar")
def confirmar_hecho(hecho_id: int, _: Annotated[dict, Depends(requiere_rol(*QUIEN_APRUEBA, accion="confirmar hechos de la memoria"))], conn: Conexion) -> dict:
    _con_error_de_memoria(lambda: memoria.confirmar(conn, hecho_id))
    return _hecho(next(h for h in memoria.listar(conn) if h["id"] == hecho_id))


@router.delete("/memoria/{hecho_id}", status_code=204)
def borrar_hecho(hecho_id: int, _: Annotated[dict, Depends(requiere_rol(*QUIEN_APRUEBA, accion="borrar hechos de la memoria"))], conn: Conexion) -> None:
    _con_error_de_memoria(lambda: memoria.borrar(conn, hecho_id))


# --------------------------------------------------------------------------- bitácora
@router.get("/bitacora")
def listar_bitacora(usuario: Usuario, conn: Conexion, limite: int = 200) -> list[dict]:
    """Un Vendedor ve solo sus propias entradas; los demás roles ven todas."""
    filas = bitacora.listar(conn, max(1, min(limite, 1000)))
    if usuario["rol"] == VENDEDOR:
        filas = [f for f in filas if f["usuario"] == usuario["nombre"]]
    return [
        {"id": str(f["id"]), "fecha": f["fecha"], "usuario": f["usuario"], "pregunta": f["pregunta"], "documentos": f["documentos"],
         "herramientas": f["herramientas"], "duracion_ms": f["duracion_ms"], "cotizacion": f["cotizacion"], "aprobado_por": f["aprobado_por"]}
        for f in filas
    ]


# --------------------------------------------------------------------------- ajustes
def _ultima_evaluacion() -> dict | None:
    archivos = sorted(RESULTADOS.glob("*.json")) if RESULTADOS.exists() else []
    for ruta in reversed(archivos):
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
            r = d["resumen"]
            return {"archivo": ruta.name, "fecha": d["fecha"], "embedder": d["embedder"], "mediana_ms": r["mediana_ms"], "p95_ms": r["p95_ms"],
                    "exactitud": r["exactitud"], "casos": len(d["casos"]), "aprobado": d["aprobado"]}
        except (OSError, ValueError, KeyError):
            continue
    return None


@router.get("/ajustes")
def ajustes(_: Usuario, conn: Conexion) -> dict:
    """Solo lectura: modelo, embedder, modo demo, índice y latencia medida (la de la última cotización y la de la evaluación)."""
    config = ConfigLLM()
    modelo = {"ollama": config.ollama_model, "groq": config.groq_model}.get(config.llm_provider) or ", ".join(config.modelos_openrouter)
    return {
        "proveedor": config.llm_provider, "modelo": modelo, "modo_demo": config.modo_demo,
        "embedder": (os.environ.get("TESSERA_EMBEDDER") or "e5"),
        "fragmentos_indexados": conn.execute("SELECT COUNT(*) FROM fragmentos").fetchone()[0],
        "ultima_cotizacion_ms": _ultima["tiempos_ms"], "evaluacion": _ultima_evaluacion(),
        "cotizaciones": conn.execute("SELECT COUNT(*) FROM cotizaciones").fetchone()[0],
        "hechos_memoria": conn.execute("SELECT COUNT(*) FROM memoria").fetchone()[0],
    }


@router.delete("/datos")
def borrar_datos(_: Annotated[dict, Depends(requiere_rol(ADMINISTRADOR, accion="borrar los datos de trabajo"))], conn: Conexion) -> dict:
    """Borra cotizaciones, aprobaciones, memoria y bitácora. NO toca las fuentes cargadas ni los usuarios. No se puede deshacer."""
    conteo = {
        "cotizaciones": conn.execute("SELECT COUNT(*) FROM cotizaciones").fetchone()[0],
        "hechos_memoria": conn.execute("SELECT COUNT(*) FROM memoria").fetchone()[0],
        "entradas_bitacora": conn.execute("SELECT COUNT(*) FROM bitacora").fetchone()[0],
    }
    for tabla in ("aprobaciones", "cotizacion_historial", "cotizacion_partidas", "cotizacion_escenarios", "cotizaciones", "memoria", "bitacora"):
        conn.execute(f"DELETE FROM {tabla}")
    conn.commit()
    return {"ok": True, "borrado": conteo}
