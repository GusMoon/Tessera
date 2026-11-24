"""Ruta de chat con el LLM (modo prueba): conversación + archivos e imágenes adjuntas.

Endpoints:
- POST /api/chat         multipart: `mensaje`, `historial` (JSON), `archivos` (0..N). Devuelve la respuesta del modelo.
- GET  /api/chat/config  proveedor y modelos configurados (nunca la clave).
- GET  /api/chat/uso     peticiones gratuitas que quedan hoy, cuándo se reinicia y tokens consumidos en la sesión.

Alcance actual: el modelo responde SOLO con lo que se le adjunta en la conversación. Todavía no consulta la base
ni usa `calcular_cotizacion` (reglas 1 y 2 de CLAUDE.md quedan pendientes de `retrieval/` y `agent/tools/`).
Los archivos se leen en memoria y no se guardan en disco ni en la base (regla 7).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Optional

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from agent.llm import (
    PROMPT_SISTEMA_COTIZACIONES,
    ConfigLLM,
    ErrorAutenticacionLLM,
    ErrorConfiguracionLLM,
    ErrorLimiteLLM,
    ErrorLLM,
    ErrorModeloNoDisponibleLLM,
    ErrorRedLLM,
    ProveedorLLM,
    crear_proveedor,
)
from agent.contexto import describir_fuentes
from agent.llm.adjuntos import MAX_BYTES_ARCHIVO, Adjunto, ErrorAdjunto, construir_contenido, leer_adjunto_bytes
from agent.llm.uso import LIMITE_POR_MINUTO, CuotaOpenRouter, VentanaMinuto, proximo_reinicio_diario
from db.database import get_connection

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_ARCHIVOS = 5
MAX_MENSAJES_HISTORIAL = 20
# Los modelos de razonamiento (p. ej. ERNIE) gastan tokens pensando; con 512 la respuesta suele llegar vacía.
MIN_TOKENS_SALIDA = 2048
# Groq limita por tokens por minuto (8,000 en gpt-oss-20b, según su documentación) y cuenta lo pedido: un tope
# de salida alto casi agota el minuto con una sola petición. Con reasoning_effort bajo, 1,024 alcanza.
MIN_TOKENS_SALIDA_GROQ = 1024

_proveedores: dict[str, ProveedorLLM] = {}
_candado = threading.Lock()
_cuota = CuotaOpenRouter()  # caché corta de la cuota de la clave
_minuto = VentanaMinuto()  # peticiones de esta app en el último minuto


# --------------------------------------------------------------------------- modelos
class AdjuntoInfo(BaseModel):
    nombre: str
    tipo: str
    detalle: str
    truncado: bool


class RespuestaChat(BaseModel):
    texto: str
    modelo: str  # el que realmente respondió
    proveedor: str
    latencia_s: float
    tokens_entrada: int
    tokens_salida: int
    adjuntos: list[AdjuntoInfo]
    avisos: list[str]


class SolicitudesDia(BaseModel):
    usadas: Optional[int] = None
    limite: Optional[int] = None
    restantes: Optional[int] = None


class EstimacionMinuto(BaseModel):
    usadas_aqui: int  # peticiones de ESTA aplicación en el último minuto (estimación)
    limite: int
    segundos_para_liberar: Optional[int] = None


class TokensMinuto(BaseModel):
    """Solo Groq: lo que informó en la última respuesta (los tokens sí se limitan por minuto allí)."""
    restantes: Optional[int] = None
    limite: Optional[int] = None
    segundos_para_reiniciar: Optional[float] = None


class UsoSesion(BaseModel):
    llamadas: int
    tokens_entrada: int
    tokens_salida: int
    tokens_total: int


class UsoChat(BaseModel):
    proveedor: str
    modelo: str
    tipo_limite: str  # "peticiones" (OpenRouter :free) | "peticiones y tokens" (Groq) | "ninguno" (Ollama local)
    plan_gratuito: Optional[bool] = None
    dia: Optional[SolicitudesDia] = None
    reinicio_dia_utc: Optional[str] = None  # ISO 8601 UTC del próximo reinicio (ver `reinicio_modo`)
    # "dia_utc": se reinicia a las 00:00 UTC (OpenRouter). "recarga": la cuota se recarga de forma continua y esta
    # fecha es cuándo vuelve a estar completa (Groq; medido: 1 petición gastada tarda ~86 s, 2 tardan ~173 s).
    reinicio_modo: Optional[str] = None
    minuto: Optional[EstimacionMinuto] = None
    tokens_minuto: Optional[TokensMinuto] = None
    sesion: UsoSesion  # desde que arrancó el backend
    aviso: Optional[str] = None


class ConfigChat(BaseModel):
    proveedor: str
    modelo: str
    modelo_vision: Optional[str] = None


# --------------------------------------------------------------------------- proveedor
def _config_vision(config: ConfigLLM) -> ConfigLLM:
    nombre = config.llm_provider.strip().lower()
    if nombre == "openrouter":
        modelo, campo = config.openrouter_model_vision.strip(), "openrouter_models"
    elif nombre == "ollama":
        modelo, campo = config.ollama_model_vision.strip(), "ollama_model"
    elif nombre == "groq":
        # Groq no ofrece hoy un modelo de visión con plan gratuito: las imágenes se envían por OpenRouter.
        modelo = config.openrouter_model_vision.strip()
        if not config.openrouter_api_key.get_secret_value().strip() or not modelo:
            raise ErrorConfiguracionLLM(
                "Adjuntaste una imagen y Groq no tiene un modelo de visión gratuito. Para imágenes se usa OpenRouter: "
                "define OPENROUTER_API_KEY (y opcionalmente OPENROUTER_MODEL_VISION) en tu archivo .env."
            )
        return config.model_copy(update={"llm_provider": "openrouter", "openrouter_models": modelo})
    else:
        return config  # `crear_proveedor` explicará que el proveedor no es válido
    if not modelo:
        raise ErrorConfiguracionLLM(
            "Adjuntaste una imagen pero no hay un modelo de visión configurado. "
            "Define OPENROUTER_MODEL_VISION (o OLLAMA_MODEL_VISION) en tu archivo .env."
        )
    return config.model_copy(update={campo: modelo})


def _obtener_proveedor(vision: bool) -> ProveedorLLM:
    """Un proveedor por tipo de petición (texto / visión), creado al primer uso y reutilizado."""
    clave = "vision" if vision else "texto"
    with _candado:
        if clave not in _proveedores:
            config = ConfigLLM()
            _proveedores[clave] = crear_proveedor(_config_vision(config) if vision else config)
        return _proveedores[clave]


def _max_tokens_salida(proveedor: str = "") -> int | None:
    """Tope de salida para el proveedor que va a responder (el de visión puede ser otro que el de texto)."""
    tope = ConfigLLM().llm_max_tokens_salida
    minimo = MIN_TOKENS_SALIDA_GROQ if proveedor == "groq" else MIN_TOKENS_SALIDA
    return max(tope, minimo) if tope > 0 else None  # 0 = sin tope, se respeta


_ESTADO_ERROR: dict[type[ErrorLLM], int] = {
    ErrorConfiguracionLLM: 503,
    ErrorLimiteLLM: 429,
    ErrorRedLLM: 503,
    ErrorAutenticacionLLM: 502,
    ErrorModeloNoDisponibleLLM: 502,
}


def _estado_http(exc: ErrorLLM) -> int:
    for clase, estado in _ESTADO_ERROR.items():
        if isinstance(exc, clase):
            return estado
    return 502


# --------------------------------------------------------------------------- entrada
def _parsear_historial(crudo: str) -> list[dict[str, str]]:
    try:
        datos = json.loads(crudo or "[]")
        if not isinstance(datos, list):
            raise ValueError
        mensajes = []
        for m in datos:
            rol = {"usuario": "user", "tessera": "assistant"}[m["rol"]]
            texto = m["texto"]
            if not isinstance(texto, str):
                raise ValueError
            if texto.strip():
                mensajes.append({"role": rol, "content": texto})
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="El historial no tiene el formato esperado.") from None
    return mensajes[-MAX_MENSAJES_HISTORIAL:]


def _leer_archivos(archivos: list[UploadFile]) -> list[Adjunto]:
    if len(archivos) > MAX_ARCHIVOS:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_ARCHIVOS} archivos por mensaje.")
    adjuntos = []
    for f in archivos:
        nombre = f.filename or "archivo"
        datos = f.file.read(MAX_BYTES_ARCHIVO + 1)  # un byte de más basta para detectar que excede el límite
        try:
            adjuntos.append(leer_adjunto_bytes(nombre, datos))
        except ErrorAdjunto as exc:
            motivo = str(exc)
            raise HTTPException(status_code=400, detail=motivo if nombre in motivo else f"{nombre}: {motivo}") from None
    return adjuntos


def _prompt_con_fuentes(usuario_id: Optional[str]) -> str:
    """El prompt de sistema más lo que hay cargado para este usuario; sin usuario, el prompt de siempre."""
    if not usuario_id:
        return PROMPT_SISTEMA_COTIZACIONES
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM usuarios WHERE id = ?", (usuario_id,)).fetchone() is None:
            return PROMPT_SISTEMA_COTIZACIONES
        return f"{PROMPT_SISTEMA_COTIZACIONES}\n{describir_fuentes(conn, usuario_id)}"
    finally:
        conn.close()


# --------------------------------------------------------------------------- rutas
@router.get("/config", response_model=ConfigChat)
def configuracion_chat():
    config = ConfigLLM()
    if config.llm_provider.strip().lower() == "groq":
        con_vision = bool(config.openrouter_api_key.get_secret_value().strip())  # las imágenes salen por OpenRouter
        return ConfigChat(
            proveedor="groq", modelo=config.groq_model, modelo_vision=config.openrouter_model_vision.strip() or None if con_vision else None
        )
    if config.llm_provider.strip().lower() == "openrouter":
        modelos = config.modelos_openrouter
        return ConfigChat(
            proveedor="openrouter",
            modelo=modelos[0] if modelos else "(sin configurar)",
            modelo_vision=config.openrouter_model_vision.strip() or None,
        )
    return ConfigChat(
        proveedor=config.llm_provider, modelo=config.ollama_model, modelo_vision=config.ollama_model_vision.strip() or None
    )


def _uso_de_sesion() -> UsoSesion:
    with _candado:
        usos = [p.uso for p in _proveedores.values()]
    entrada = sum(u.tokens_entrada for u in usos)
    salida = sum(u.tokens_salida for u in usos)
    return UsoSesion(llamadas=sum(u.llamadas for u in usos), tokens_entrada=entrada, tokens_salida=salida, tokens_total=entrada + salida)


def _uso_groq(config: ConfigLLM) -> UsoChat:
    """Groq informa lo que queda en las cabeceras de cada respuesta: peticiones por día y tokens por minuto.
    Antes del primer mensaje no hay datos (no se gasta una petición solo para leerlos)."""
    base = dict(proveedor="groq", modelo=config.groq_model, tipo_limite="peticiones y tokens", sesion=_uso_de_sesion())
    try:
        limites = _obtener_proveedor(vision=False).limites  # crear el proveedor no hace llamadas a la red
    except ErrorLLM as exc:
        return UsoChat(**base, aviso=str(exc))
    d = limites.instantanea() if limites else None
    if d is None:
        return UsoChat(**base, aviso="Groq informa la cuota en cada respuesta: envía un mensaje para verla.")
    dia = None
    reinicio = None
    if d["limite_peticiones_dia"] is not None and d["restantes_peticiones_dia"] is not None:
        dia = SolicitudesDia(
            usadas=d["limite_peticiones_dia"] - d["restantes_peticiones_dia"],
            limite=d["limite_peticiones_dia"], restantes=d["restantes_peticiones_dia"],
        )
        if d["reinicio_peticiones_s"] is not None:
            reinicio = datetime.fromtimestamp(time.time() + d["reinicio_peticiones_s"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tokens = TokensMinuto(
        restantes=d["restantes_tokens_minuto"], limite=d["limite_tokens_minuto"],
        segundos_para_reiniciar=None if d["reinicio_tokens_s"] is None else round(d["reinicio_tokens_s"], 1),
    )
    return UsoChat(**base, dia=dia, reinicio_dia_utc=reinicio, reinicio_modo="recarga" if reinicio else None, tokens_minuto=tokens)


@router.get("/uso", response_model=UsoChat)
def uso_chat():
    """Cuánto queda de la cuota gratuita y cuándo se reinicia. OpenRouter limita los modelos :free por
    peticiones, no por tokens, así que lo que queda se expresa en peticiones; los tokens son solo informativos."""
    config = ConfigLLM()
    if config.llm_provider.strip().lower() == "groq":
        return _uso_groq(config)
    sesion = _uso_de_sesion()
    if config.llm_provider.strip().lower() != "openrouter":
        return UsoChat(
            proveedor=config.llm_provider, modelo=config.ollama_model, tipo_limite="ninguno", sesion=sesion,
            aviso="Modelo local: no hay límite de peticiones ni de tokens (solo el de tu equipo).",
        )
    modelos = config.modelos_openrouter
    base = dict(proveedor="openrouter", modelo=modelos[0] if modelos else "(sin configurar)", tipo_limite="peticiones", sesion=sesion)
    usadas_aqui, liberar = _minuto.estado()
    minuto = EstimacionMinuto(usadas_aqui=usadas_aqui, limite=LIMITE_POR_MINUTO, segundos_para_liberar=liberar)
    clave = config.openrouter_api_key.get_secret_value().strip()
    cuota = _cuota.consultar(clave) if clave else None
    if cuota is None:
        return UsoChat(**base, minuto=minuto, aviso="No se pudo consultar la cuota en OpenRouter (sin conexión o clave inválida).")
    return UsoChat(
        **base,
        plan_gratuito=cuota["plan_gratuito"],
        dia=SolicitudesDia(usadas=cuota["usadas"], limite=cuota["limite"], restantes=cuota["restantes"]),
        reinicio_dia_utc=proximo_reinicio_diario(datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        reinicio_modo="dia_utc",
        minuto=minuto,
    )


@router.post("", response_model=RespuestaChat)
def chatear(
    mensaje: str = Form(...),
    historial: str = Form("[]"),
    archivos: Optional[list[UploadFile]] = File(None),
    x_usuario_id: Optional[str] = Header(None),
):
    texto = mensaje.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El mensaje está vacío.")
    mensajes = _parsear_historial(historial)
    adjuntos = _leer_archivos(archivos or [])
    mensajes.append({"role": "user", "content": construir_contenido(texto, adjuntos)})

    try:
        proveedor = _obtener_proveedor(vision=any(a.tipo == "imagen" for a in adjuntos))
        _minuto.registrar()
        r = proveedor.completar(mensajes, sistema=_prompt_con_fuentes(x_usuario_id), max_tokens=_max_tokens_salida(proveedor.nombre))
    except ErrorLLM as exc:
        espera = getattr(exc, "reintentar_en_s", None)
        raise HTTPException(
            status_code=_estado_http(exc), detail=str(exc), headers={"Retry-After": str(espera)} if espera else None
        ) from None
    finally:
        _cuota.invalidar()  # el contador de OpenRouter cambió: la próxima consulta debe ser fresca

    avisos = [f"{a.nombre} se recortó a {len(a.texto):,} de {a.caracteres_originales:,} caracteres." for a in adjuntos if a.truncado]
    respuesta = r.texto.strip()
    if not respuesta:
        avisos.append("El modelo devolvió una respuesta vacía (los modelos de razonamiento pueden agotar el tope de tokens). Reintenta.")
    return RespuestaChat(
        texto=respuesta,
        modelo=r.modelo,
        proveedor=r.proveedor,
        latencia_s=round(r.latencia_s, 2),
        tokens_entrada=r.tokens_entrada,
        tokens_salida=r.tokens_salida,
        adjuntos=[AdjuntoInfo(nombre=a.nombre, tipo=a.tipo, detalle=a.detalle, truncado=a.truncado) for a in adjuntos],
        avisos=avisos,
    )
