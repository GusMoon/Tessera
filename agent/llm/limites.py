"""Límites que Groq informa en las cabeceras de CADA respuesta (documentación de Groq, 23/11/2026):

- ``x-ratelimit-limit-requests`` / ``-remaining-requests`` / ``-reset-requests``: peticiones por DÍA (RPD).
- ``x-ratelimit-limit-tokens`` / ``-remaining-tokens`` / ``-reset-tokens``: tokens por MINUTO (TPM).
- Los reinicios vienen como duración («2m59.56s», «7.66s»). El tope diario de tokens (TPD) no viene en cabeceras.
- Estos valores describen la organización, no solo esta app, así que son más fiables que una cuenta propia.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Mapping

_DURACION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_SEGUNDOS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parsear_duracion(texto: str | None) -> float | None:
    """«2m59.56s» → 179.56; «7.66s» → 7.66; «250ms» → 0.25; None si no es interpretable."""
    if not texto:
        return None
    partes = _DURACION.findall(texto.strip())
    if not partes or "".join(n + u for n, u in partes) != texto.strip():
        return None
    return sum(float(n) * _SEGUNDOS[u] for n, u in partes)


def _entero(valor: Any) -> int | None:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


class LimitesGroq:
    """Guarda lo que informó la última respuesta de Groq. Seguro entre hilos."""

    def __init__(self) -> None:
        self._candado = threading.Lock()
        self._datos: dict[str, Any] | None = None

    def registrar_respuesta(self, respuesta: Any) -> None:
        """Gancho de httpx (`event_hooks['response']`): lee las cabeceras sin tocar el cuerpo."""
        self.actualizar(getattr(respuesta, "headers", {}), time.time())

    def actualizar(self, cabeceras: Mapping[str, str], ahora: float) -> None:
        h = {str(k).lower(): v for k, v in cabeceras.items()}
        if "x-ratelimit-remaining-tokens" not in h and "x-ratelimit-remaining-requests" not in h:
            return  # una respuesta sin cabeceras de límite (p. ej. un error ajeno) no borra lo último conocido
        with self._candado:
            self._datos = {
                "capturado_en": ahora,
                "limite_peticiones_dia": _entero(h.get("x-ratelimit-limit-requests")),
                "restantes_peticiones_dia": _entero(h.get("x-ratelimit-remaining-requests")),
                "reinicio_peticiones_s": parsear_duracion(h.get("x-ratelimit-reset-requests")),
                "limite_tokens_minuto": _entero(h.get("x-ratelimit-limit-tokens")),
                "restantes_tokens_minuto": _entero(h.get("x-ratelimit-remaining-tokens")),
                "reinicio_tokens_s": parsear_duracion(h.get("x-ratelimit-reset-tokens")),
            }

    def instantanea(self, ahora: float | None = None) -> dict[str, Any] | None:
        """Último dato conocido con los reinicios ya descontados el tiempo transcurrido; None si aún no hay."""
        with self._candado:
            if self._datos is None:
                return None
            d = dict(self._datos)
        ahora = time.time() if ahora is None else ahora
        pasado = max(0.0, ahora - d["capturado_en"])
        for clave in ("reinicio_peticiones_s", "reinicio_tokens_s"):
            if d[clave] is not None:
                d[clave] = max(0.0, d[clave] - pasado)
        # Si la ventana de tokens ya se reinició, el último «restante» quedó viejo: vuelve al tope.
        if d["reinicio_tokens_s"] == 0.0 and d["limite_tokens_minuto"] is not None:
            d["restantes_tokens_minuto"] = d["limite_tokens_minuto"]
        return d
