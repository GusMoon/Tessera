"""Utilidades para que una clave de API nunca aparezca completa en mensajes ni logs."""

from __future__ import annotations

_PREFIJO_PUBLICO = "sk-or-v1-"  # prefijo fijo de OpenRouter; no es secreto
_MIN_LARGO_VISIBLE = 12  # por debajo de esto no se muestra ningún carácter


def enmascarar(clave: str | None) -> str:
    """Devuelve la clave oculta, p. ej. ``sk-or-v1-…f668``. Nunca la devuelve completa."""
    if not clave:
        return "(vacía)"
    if len(clave) < _MIN_LARGO_VISIBLE:
        return "***"
    prefijo = _PREFIJO_PUBLICO if clave.startswith(_PREFIJO_PUBLICO) else ""
    return f"{prefijo}…{clave[-4:]}"


def redactar(texto: str, clave: str | None) -> str:
    """Reemplaza cualquier aparición de la clave dentro de ``texto`` por su versión enmascarada.

    Los SDK y los proveedores a veces repiten la clave (o parte de ella) en sus mensajes
    de error; todo texto externo debe pasar por aquí antes de mostrarse.
    """
    if not clave or not texto:
        return texto
    return texto.replace(clave, enmascarar(clave))
