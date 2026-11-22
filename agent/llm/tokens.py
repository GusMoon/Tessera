"""Gestión de tokens: estimación barata, recorte de historial y contador de uso.

La estimación es una heurística para decidir cuánto historial enviar; el conteo real
sale del campo ``usage`` de cada respuesta (ver `UsoAcumulado`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# [Suposición] ~3 caracteres por token en español con tokenizadores BPE típicos: sobreestima un poco,
# lo cual es lo seguro para no pasarse del contexto. Se afinará comparando con `usage` real.
_CARACTERES_POR_TOKEN = 3.0
_SOBRECOSTO_MENSAJE = 4  # tokens fijos por mensaje (rol y delimitadores)


def estimar_tokens(texto: str) -> int:
    return int(len(texto) / _CARACTERES_POR_TOKEN) + 1 if texto else 0


_TOKENS_POR_IMAGEN = 800  # [Suposición] costo típico de una imagen; el base64 NO se cuenta como texto


def _tokens_mensaje(m: dict[str, Any]) -> int:
    contenido = m.get("content") or ""
    if isinstance(contenido, list):  # contenido multimodal: partes {"type": "text"|"image_url", ...}
        total = 0
        for parte in contenido:
            if isinstance(parte, dict) and parte.get("type") == "text":
                total += estimar_tokens(str(parte.get("text") or ""))
            else:
                total += _TOKENS_POR_IMAGEN
        return total + _SOBRECOSTO_MENSAJE
    return estimar_tokens(str(contenido)) + _SOBRECOSTO_MENSAJE


def recortar_historial(mensajes: list[dict[str, Any]], presupuesto: int) -> list[dict[str, Any]]:
    """Conserva los mensajes ``system`` y los turnos más recientes que quepan en ``presupuesto`` tokens.

    - Los mensajes ``system`` nunca se descartan.
    - El último mensaje (la pregunta actual) siempre se conserva, aunque por sí solo exceda el presupuesto.
    - Se descartan primero los turnos más antiguos; el orden cronológico se respeta.
    Nota: descartar no resume. Resumir el historial viejo corresponde a la memoria (agent/memory).
    """
    if presupuesto <= 0 or not mensajes:
        return list(mensajes)
    fijos = [i for i, m in enumerate(mensajes) if m.get("role") == "system"]
    gastado = sum(_tokens_mensaje(mensajes[i]) for i in fijos)
    conservar = set(fijos)
    for i in range(len(mensajes) - 1, -1, -1):
        if i in conservar:
            continue
        costo = _tokens_mensaje(mensajes[i])
        es_ultimo = i == len(mensajes) - 1
        if es_ultimo or gastado + costo <= presupuesto:
            conservar.add(i)
            gastado += costo
        else:
            break  # no se saltan turnos para no dejar el diálogo con huecos
    return [m for i, m in enumerate(mensajes) if i in conservar]


@dataclass
class UsoAcumulado:
    """Tokens reales (según ``usage`` del proveedor) acumulados por un proveedor desde que se creó."""

    llamadas: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0

    @property
    def total(self) -> int:
        return self.tokens_entrada + self.tokens_salida

    def registrar(self, entrada: int, salida: int) -> None:
        self.llamadas += 1
        self.tokens_entrada += entrada
        self.tokens_salida += salida
