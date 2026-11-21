"""Proveedores de LLM con una interfaz única compatible con OpenAI.

Uso:
    proveedor = crear_proveedor()          # lee LLM_PROVIDER y el resto del entorno / .env
    respuesta = proveedor.completar([{"role": "user", "content": "Hola"}])
    respuesta.texto, respuesta.modelo      # `modelo` es el que realmente respondió

Regla 1 de CLAUDE.md: el modelo redacta y explica; no calcula precios ni totales.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import openai
from openai import OpenAI

from .config import ConfigLLM
from .seguridad import enmascarar, redactar
from .tokens import UsoAcumulado, recortar_historial

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PROVEEDORES = ("ollama", "openrouter")
_TIMEOUT_SEGUNDOS = 120.0  # un modelo de 3B en CPU puede tardar; se ajustará con la medición de latencia
_MAX_REINTENTOS = 1


# --------------------------------------------------------------------------- errores
class ErrorLLM(Exception):
    """Error legible para el usuario. Su mensaje nunca contiene la clave."""


class ErrorConfiguracionLLM(ErrorLLM):
    """La configuración del proveedor es inválida o está incompleta."""


class ErrorAutenticacionLLM(ErrorLLM):
    """401: clave inválida o ausente."""


class ErrorLimiteLLM(ErrorLLM):
    """429: se alcanzó el límite de uso."""


class ErrorModeloNoDisponibleLLM(ErrorLLM):
    """El modelo (o todos los de la lista) no está disponible."""


class ErrorRedLLM(ErrorLLM):
    """No hubo conexión con el proveedor."""


# --------------------------------------------------------------------------- resultado
@dataclass(frozen=True)
class RespuestaLLM:
    texto: str
    modelo: str  # campo `model` de la respuesta: el modelo que realmente respondió
    proveedor: str
    latencia_s: float
    tokens_entrada: int = 0  # según `usage` del proveedor; 0 si no lo reporta
    tokens_salida: int = 0


# --------------------------------------------------------------------------- proveedor
@dataclass
class ProveedorLLM:
    nombre: str
    modelos: list[str]  # en openrouter, todos en orden de failover; en ollama, uno solo
    _cliente: OpenAI = field(repr=False)
    _extra_body: dict[str, Any] | None = field(default=None, repr=False)
    _clave: str = field(default="", repr=False)  # solo para redactar mensajes; nunca se imprime
    # Límites de tokens (ver ConfigLLM). Un valor <= 0 o None desactiva el límite correspondiente.
    _max_tokens: int | None = field(default=None, repr=False)
    _temperatura: float | None = field(default=None, repr=False)
    _contexto_entrada: int = field(default=0, repr=False)
    uso: UsoAcumulado = field(default_factory=UsoAcumulado)

    def completar(
        self,
        mensajes: list[dict[str, Any]],
        *,
        sistema: str | None = None,
        **parametros: Any,
    ) -> RespuestaLLM:
        """Envía ``mensajes`` (formato chat de OpenAI) y devuelve la respuesta con el modelo que respondió.

        Ahorro de tokens, por defecto:
        - ``max_tokens`` y ``temperature`` salen de la configuración (se pueden sobrescribir por llamada).
        - Si ``sistema`` se indica (p. ej. ``PROMPT_SISTEMA_COTIZACIONES``) se antepone como mensaje system.
        - El historial se recorta a ``LLM_CONTEXTO_ENTRADA`` tokens estimados (conserva system y lo más reciente).
        """
        if sistema:
            mensajes = [{"role": "system", "content": sistema}, *mensajes]
        mensajes = recortar_historial(mensajes, self._contexto_entrada)
        if self._max_tokens and self._max_tokens > 0:
            parametros.setdefault("max_tokens", self._max_tokens)
        if self._temperatura is not None:
            parametros.setdefault("temperature", self._temperatura)
        if self._extra_body is not None:
            parametros.setdefault("extra_body", self._extra_body)
        inicio = time.perf_counter()
        try:
            r = self._cliente.chat.completions.create(
                model=self.modelos[0], messages=mensajes, **parametros
            )
        except openai.OpenAIError as exc:
            raise self._traducir(exc) from None  # `from None`: el original podría traer la clave
        latencia = time.perf_counter() - inicio
        texto = (r.choices[0].message.content or "") if r.choices else ""
        uso = getattr(r, "usage", None)
        entrada = int(getattr(uso, "prompt_tokens", 0) or 0)
        salida = int(getattr(uso, "completion_tokens", 0) or 0)
        self.uso.registrar(entrada, salida)
        return RespuestaLLM(
            texto=texto,
            modelo=getattr(r, "model", None) or self.modelos[0],
            proveedor=self.nombre,
            latencia_s=latencia,
            tokens_entrada=entrada,
            tokens_salida=salida,
        )

    # -- traducción de errores del SDK a mensajes legibles y sin clave
    def _traducir(self, exc: openai.OpenAIError) -> ErrorLLM:
        detalle = redactar(str(exc), self._clave)
        if isinstance(exc, openai.AuthenticationError):
            if self.nombre == "openrouter":
                return ErrorAutenticacionLLM(
                    "401: OpenRouter rechazó la clave (inválida, revocada o ausente). "
                    f"Revisa OPENROUTER_API_KEY en tu archivo .env (clave actual: {enmascarar(self._clave)})."
                )
            return ErrorAutenticacionLLM(f"401: el servidor rechazó la autenticación. {detalle}")
        if isinstance(exc, openai.RateLimitError):
            return ErrorLimiteLLM(
                "429: se alcanzó el límite de uso. Los modelos gratuitos tienen límites por minuto y por día; "
                "espera unos minutos, agrega más modelos a OPENROUTER_MODELS o cambia a LLM_PROVIDER=ollama."
                if self.nombre == "openrouter"
                else f"429: el servidor está saturado. {detalle}"
            )
        if isinstance(exc, (openai.NotFoundError, openai.BadRequestError)):
            if self.nombre == "ollama":
                return ErrorModeloNoDisponibleLLM(
                    f"Ollama no tiene el modelo '{self.modelos[0]}'. Descárgalo con: ollama pull {self.modelos[0]}"
                    f" (o ajusta OLLAMA_MODEL). Detalle: {detalle}"
                )
            return ErrorModeloNoDisponibleLLM(
                "Ningún modelo de OPENROUTER_MODELS está disponible "
                f"({', '.join(self.modelos)}). Los modelos gratuitos cambian con frecuencia: "
                f"revisa los IDs en la lista de OpenRouter. Detalle: {detalle}"
            )
        if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
            destino = OPENROUTER_BASE_URL if self.nombre == "openrouter" else str(self._cliente.base_url)
            ayuda = " ¿Está corriendo Ollama (ollama serve)?" if self.nombre == "ollama" else ""
            return ErrorRedLLM(f"No hay conexión con {destino}. Revisa tu red o la URL.{ayuda}")
        if isinstance(exc, openai.APIStatusError):
            return ErrorLLM(f"El proveedor respondió con error {exc.status_code}. {detalle}")
        return ErrorLLM(f"Error inesperado del proveedor: {detalle}")


# --------------------------------------------------------------------------- fábrica
def validar_modelos_gratuitos(modelos: list[str]) -> None:
    """Los respaldos de pago generarían cobros: todos los modelos deben terminar en ``:free``."""
    de_pago = [m for m in modelos if not m.endswith(":free")]
    if de_pago:
        raise ErrorConfiguracionLLM(
            f"OPENROUTER_MODELS contiene modelos que no terminan en ':free': {', '.join(de_pago)}. "
            "Un modelo de respaldo de pago generaría cobros; usa solo modelos gratuitos."
        )


def crear_proveedor(config: ConfigLLM | None = None) -> ProveedorLLM:
    """Crea el proveedor indicado por ``LLM_PROVIDER`` (predeterminado: ``ollama``)."""
    config = config or ConfigLLM()
    nombre = config.llm_provider.strip().lower()
    if nombre == "ollama":
        return _crear_ollama(config)
    if nombre == "openrouter":
        return _crear_openrouter(config)
    raise ErrorConfiguracionLLM(
        f"LLM_PROVIDER='{config.llm_provider}' no es válido. Valores aceptados: {', '.join(PROVEEDORES)}."
    )


def _crear_ollama(config: ConfigLLM) -> ProveedorLLM:
    cliente = OpenAI(
        base_url=config.ollama_base_url,
        api_key="ollama",  # el SDK exige un valor; Ollama lo ignora. No es una credencial.
        timeout=_TIMEOUT_SEGUNDOS,
        max_retries=_MAX_REINTENTOS,
    )
    return ProveedorLLM(nombre="ollama", modelos=[config.ollama_model], _cliente=cliente, **_limites(config))


def _crear_openrouter(config: ConfigLLM) -> ProveedorLLM:
    clave = config.openrouter_api_key.get_secret_value().strip()
    if not clave:
        raise ErrorConfiguracionLLM(
            "Falta OPENROUTER_API_KEY. Crea una clave en tu cuenta de OpenRouter y pégala en tu archivo .env "
            "(nunca en el chat ni en el código)."
        )
    modelos = config.modelos_openrouter
    if not modelos:
        raise ErrorConfiguracionLLM(
            "OPENROUTER_MODELS está vacío. Llénalo en tu archivo .env con uno o más IDs de modelos "
            "gratuitos de OpenRouter separados por comas, en orden de preferencia; todos deben terminar en ':free'."
        )
    validar_modelos_gratuitos(modelos)

    cabeceras = {"X-Title": config.openrouter_title} if config.openrouter_title else {}
    if config.openrouter_referer:
        cabeceras["HTTP-Referer"] = config.openrouter_referer
    cliente = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=clave,
        default_headers=cabeceras,
        timeout=_TIMEOUT_SEGUNDOS,
        max_retries=_MAX_REINTENTOS,
    )
    # `models` activa el failover automático de OpenRouter entre los modelos de la lista.
    return ProveedorLLM(
        nombre="openrouter",
        modelos=modelos,
        _cliente=cliente,
        _extra_body={"models": modelos},
        _clave=clave,
        **_limites(config),
    )


def _limites(config: ConfigLLM) -> dict[str, Any]:
    return {
        "_max_tokens": config.llm_max_tokens_salida,
        "_temperatura": config.llm_temperatura,
        "_contexto_entrada": config.llm_contexto_entrada,
    }
