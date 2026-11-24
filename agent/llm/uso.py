"""Uso y cuota del proveedor de LLM: cuántas peticiones gratuitas quedan hoy y cuándo se reinicia.

Hechos verificados contra la documentación de OpenRouter (consultada el 23/11/2026) y la respuesta real de
``GET /api/v1/key`` de la clave del equipo:
- Los modelos ``:free`` NO limitan por tokens, limitan por **peticiones**: 20 por minuto y, por día UTC,
  50 con menos de 10 créditos comprados o 1000 con 10 o más.
- ``free_model_daily_requests`` (used / limit / remaining) informa el contador diario. El límite por minuto
  no se informa; solo llega en las cabeceras de un 429.
- El reinicio diario es a las 00:00 UTC [Probable: la documentación dice «día UTC», no da la hora de corte].
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
LIMITE_POR_MINUTO = 20  # peticiones por minuto en modelos :free (documentación de OpenRouter)
_VIGENCIA_CACHE_S = 15.0  # /key tiene límite por IP; no se consulta más seguido que esto
_TIMEOUT_S = 8.0


def proximo_reinicio_diario(ahora: datetime | None = None) -> datetime:
    """Siguiente 00:00 UTC."""
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return (ahora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


class CuotaOpenRouter:
    """Consulta (con caché corta) la cuota de la clave. Nunca devuelve ni registra la clave ni su ``label``."""

    def __init__(self) -> None:
        self._candado = threading.Lock()
        self._cache: tuple[float, dict[str, Any] | None] | None = None

    def invalidar(self) -> None:
        with self._candado:
            self._cache = None

    def consultar(self, clave: str) -> dict[str, Any] | None:
        """Datos de cuota o None si no se pudo consultar (sin red, clave inválida…)."""
        with self._candado:
            if self._cache and time.monotonic() - self._cache[0] < _VIGENCIA_CACHE_S:
                return self._cache[1]
        datos = self._pedir(clave)
        with self._candado:
            self._cache = (time.monotonic(), datos)
        return datos

    @staticmethod
    def _pedir(clave: str) -> dict[str, Any] | None:
        try:
            r = httpx.get(OPENROUTER_KEY_URL, headers={"Authorization": f"Bearer {clave}"}, timeout=_TIMEOUT_S)
            r.raise_for_status()
            d = r.json()["data"]
            diarias = d.get("free_model_daily_requests") or {}
            # Lista blanca: `label` identifica la clave y no debe salir de aquí.
            return {
                "plan_gratuito": bool(d.get("is_free_tier")),
                "usadas": diarias.get("used"),
                "limite": diarias.get("limit"),
                "restantes": diarias.get("remaining"),
            }
        except (httpx.HTTPError, KeyError, ValueError):
            return None


class VentanaMinuto:
    """Cuenta las peticiones que ESTA aplicación hizo en el último minuto (estimación: OpenRouter no informa
    el contador por minuto, y otras apps con la misma clave no se ven aquí)."""

    def __init__(self, ventana_s: float = 60.0) -> None:
        self._ventana = ventana_s
        self._marcas: deque[float] = deque()
        self._candado = threading.Lock()

    def registrar(self, ahora: float | None = None) -> None:
        with self._candado:
            self._marcas.append(time.monotonic() if ahora is None else ahora)

    def estado(self, ahora: float | None = None) -> tuple[int, int | None]:
        """(peticiones en la ventana, segundos hasta que la más antigua salga de ella; None si no hay)."""
        ahora = time.monotonic() if ahora is None else ahora
        with self._candado:
            while self._marcas and ahora - self._marcas[0] >= self._ventana:
                self._marcas.popleft()
            if not self._marcas:
                return 0, None
            return len(self._marcas), max(1, int(self._ventana - (ahora - self._marcas[0]) + 0.999))
