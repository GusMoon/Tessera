"""Rutas de cotizaciones (Hito 3): crear desde una solicitud, revisar, editar, aprobar, rechazar y descargar el PDF.

Contrato en `docs/contratos.md`; permisos por rol en `docs/permisos.md`. La identidad llega en `X-Usuario-Id`.
Los importes viajan en centavos enteros y los totales los calcula el servidor (`agent.tools.calcular_cotizacion`).
"""

from __future__ import annotations

import re
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, StrictInt

from agent import bitacora, cotizaciones as repo
from agent.llm import ConfigLLM, ErrorLLM, ProveedorLLM
from agent.orquestador import orquestar, registrar_en_bitacora
from agent.solicitud_archivos import preparar_solicitud
from api.deps import QUIEN_APRUEBA, TODOS, conexion, requiere_rol, usuario_actual
from documents.pdf import AprobacionRequerida, IntegridadError, generar_pdf
from retrieval.servicio import obtener_indice

router = APIRouter(prefix="/api/cotizaciones", tags=["cotizaciones"])

Escenario = Literal["economico", "recomendado", "premium"]
Conexion = Annotated[sqlite3.Connection, Depends(conexion)]
Usuario = Annotated[dict, Depends(usuario_actual)]
Edita = Annotated[dict, Depends(requiere_rol(*TODOS, accion="editar cotizaciones"))]
Aprueba = Annotated[dict, Depends(requiere_rol(*QUIEN_APRUEBA, accion="aprobar o rechazar cotizaciones"))]

_ultima = {"tiempos_ms": None}  # solo para la pantalla de Ajustes


def _proveedor_redaccion() -> ProveedorLLM | None:
    """LLM que redacta notas y riesgos. Si no hay uno configurado (o MODO_DEMO), la cotización sale igual sin redacción."""
    try:
        from api.chat import _obtener_proveedor

        return _obtener_proveedor(vision=False)
    except ErrorLLM:
        return None


class SolicitudCotizacion(BaseModel):
    solicitud: str = Field(min_length=1, max_length=4000)  # «Sí» también es un mensaje válido: si no pide materiales, lo atiende el chat
    cliente: str | None = Field(default=None, max_length=200)


class EdicionPartida(BaseModel):
    cantidad: StrictInt | None = None
    precio_unitario_centavos: StrictInt | None = None


class EdicionNotas(BaseModel):
    notas: str = Field(max_length=4000)


class Aprobacion(BaseModel):
    escenario: Escenario


class Rechazo(BaseModel):
    motivo: str = Field(default="", max_length=1000)


def _detalle(conn: sqlite3.Connection, cot_id: int, usuario: dict) -> dict:
    return repo.obtener(conn, cot_id, usuario["id"])


# --------------------------------------------------------------------------- crear y leer
def _crear_desde_texto(
    solicitud: str, cliente: str | None, usuario: dict, conn: sqlite3.Connection, response: Response, avisos_previos: list[str] | None = None
) -> dict:
    """Interpreta, calcula y guarda como borrador. Devuelve `tipo`: «cotizacion» (201), «aclaracion» (falta un dato: `preguntas`)
    o «conversacion» (no pide materiales con cantidad: que la atienda el chat)."""
    if conn.execute("SELECT COUNT(*) FROM catalogo").fetchone()[0] == 0:
        raise HTTPException(status_code=409, detail="No hay fuentes cargadas. Carga el catálogo en la pantalla Fuentes antes de cotizar.")
    indice = obtener_indice(conn)
    resultado = orquestar(
        solicitud, usuario["id"], conn, indice,
        proveedor=None if ConfigLLM().modo_demo else _proveedor_redaccion(), registrar_bitacora=False,
    )
    _ultima["tiempos_ms"] = resultado["tiempos_ms"]
    es_cotizacion = any(r["cantidad"] is not None for r in resultado["renglones"])
    if resultado["estado"] != "completa" and not es_cotizacion:
        return {"tipo": "conversacion", **({"avisos": avisos_previos} if avisos_previos else {})}
    registrar_en_bitacora(conn, usuario["id"], resultado)
    base = {"avisos": [*(avisos_previos or []), *resultado["avisos"]], "tiempos_ms": resultado["tiempos_ms"], "redaccion": {
        "origen": resultado["redaccion"]["origen"], "modelo": resultado["redaccion"]["modelo"], "aviso": resultado["redaccion"]["aviso"]}}
    if resultado["estado"] != "completa":
        return {"tipo": "aclaracion", "preguntas": resultado["preguntas"], **base}
    cot_id = repo.crear(conn, resultado, usuario["id"], solicitud, cliente)
    conn.execute("UPDATE bitacora SET cotizacion = ? WHERE id = ?", (f"#{cot_id:04d}", resultado["bitacora_id"]))
    conn.commit()
    response.status_code = 201
    return {"tipo": "cotizacion", "cotizacion": _detalle(conn, cot_id, usuario), **base}


@router.post("", status_code=200)
def crear(cuerpo: SolicitudCotizacion, response: Response, usuario: Edita, conn: Conexion) -> dict:
    """Interpreta la solicitud escrita en el chat (ver `_crear_desde_texto`)."""
    return _crear_desde_texto(cuerpo.solicitud, cuerpo.cliente, usuario, conn, response)


@router.post("/desde-archivos", status_code=200)
def crear_desde_archivos(
    response: Response, usuario: Edita, conn: Conexion, mensaje: str = Form(""), archivos: list[UploadFile] = File(...)
) -> dict:
    """Cotiza lo que piden los archivos adjuntos (PDF, Excel, CSV o texto de chat), solos o junto con el mensaje.
    Las cifras las calcula el mismo código determinista que `POST /api/cotizaciones`; los archivos solo se leen en memoria
    (no se guardan). Si no traen renglones con cantidad, responde `tipo: «conversacion»` y el chat los atiende (p. ej. una imagen)."""
    from api.chat import _leer_archivos

    adjuntos = _leer_archivos(archivos)
    pedido = preparar_solicitud(mensaje, adjuntos)
    if pedido.renglones == 0 and not re.search(r"\d", mensaje):
        return {"tipo": "conversacion", "avisos": pedido.avisos}
    nombres = ", ".join(a.nombre for a in adjuntos if a.tipo == "texto")
    return _crear_desde_texto(pedido.texto, pedido.cliente, usuario, conn, response, [f"Se leyeron los archivos: {nombres}.", *pedido.avisos])


@router.get("")
def listar(usuario: Usuario, conn: Conexion) -> list[dict]:
    return repo.listar(conn, usuario["id"])


@router.get("/{cot_id}")
def detalle(cot_id: int, usuario: Usuario, conn: Conexion) -> dict:
    return _detalle(conn, cot_id, usuario)


# --------------------------------------------------------------------------- editar
@router.patch("/{cot_id}/partidas/{partida_id}")
def editar_partida(cot_id: int, partida_id: int, cuerpo: EdicionPartida, usuario: Edita, conn: Conexion) -> dict:
    """Cambia cantidad o precio unitario. El servidor valida y es la fuente de verdad de los totales."""
    repo.editar_partida(conn, cot_id, partida_id, usuario, cuerpo.cantidad, cuerpo.precio_unitario_centavos)
    return _detalle(conn, cot_id, usuario)


@router.patch("/{cot_id}/escenarios/{escenario}")
def editar_notas(cot_id: int, escenario: Escenario, cuerpo: EdicionNotas, usuario: Edita, conn: Conexion) -> dict:
    repo.editar_notas(conn, cot_id, escenario, cuerpo.notas, usuario)
    return _detalle(conn, cot_id, usuario)


# --------------------------------------------------------------------------- estados
@router.post("/{cot_id}/enviar")
def enviar(cot_id: int, usuario: Edita, conn: Conexion) -> dict:
    repo.enviar_a_revision(conn, cot_id, usuario)
    return _detalle(conn, cot_id, usuario)


@router.post("/{cot_id}/aprobar")
def aprobar(cot_id: int, cuerpo: Aprobacion, usuario: Aprueba, conn: Conexion) -> dict:
    """Registra la aprobación (sin ella no hay PDF). Solo Responsable comercial o Administrador."""
    repo.aprobar(conn, cot_id, cuerpo.escenario, usuario)
    detalle = _detalle(conn, cot_id, usuario)
    bitacora.registrar(
        conn, usuario["id"], f"Aprobación de la cotización {detalle['folio']}", sorted(detalle["fuentes"]), ["aprobar"], 0,
        cotizacion=detalle["folio"], aprobado_por=usuario["nombre"],
    )
    return detalle


@router.post("/{cot_id}/rechazar")
def rechazar(cot_id: int, cuerpo: Rechazo, usuario: Aprueba, conn: Conexion) -> dict:
    repo.rechazar(conn, cot_id, cuerpo.motivo, usuario)
    return _detalle(conn, cot_id, usuario)


# --------------------------------------------------------------------------- PDF
@router.get("/{cot_id}/pdf")
def descargar_pdf(cot_id: int, usuario: Usuario, conn: Conexion) -> Response:
    """PDF de la cotización aprobada. Sin aprobación registrada responde 409 y no genera nada (regla 3)."""
    detalle = _detalle(conn, cot_id, usuario)  # 404 si no existe
    try:
        contenido = generar_pdf(conn, cot_id)
    except AprobacionRequerida as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except IntegridadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    bitacora.registrar(
        conn, usuario["id"], f"PDF de la cotización {detalle['folio']}", sorted(detalle["fuentes"]), ["generar_pdf"], 0,
        cotizacion=detalle["folio"], aprobado_por=detalle["aprobada_por"],
    )
    nombre = f"Cotizacion-{detalle['folio'].lstrip('#')}.pdf"
    return Response(content=contenido, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
