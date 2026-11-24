"""Identidad y permisos por rol de la API (prototipo).

La identidad llega en la cabecera `X-Usuario-Id` (ids de la tabla `usuarios`). NO es autenticación real: no hay
contraseñas ni sesiones, así que cualquiera que conozca un id puede usarlo. Sirve para probar los permisos por rol;
antes de producción hay que reemplazarla (decisiones abiertas 1 y 6). La matriz está en `docs/permisos.md`.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException

from db.database import get_connection

VENDEDOR = "Vendedor"
RESPONSABLE = "Responsable comercial"
ADMINISTRADOR = "Administrador"
TODOS = (VENDEDOR, RESPONSABLE, ADMINISTRADOR)
QUIEN_APRUEBA = (RESPONSABLE, ADMINISTRADOR)


def usuario_actual(x_usuario_id: Annotated[str | None, Header()] = None) -> dict:
    if not x_usuario_id:
        raise HTTPException(status_code=401, detail="Falta indicar quién eres (cabecera X-Usuario-Id). Elige un usuario en la interfaz.")
    conn = get_connection()
    try:
        fila = conn.execute("SELECT id, nombre, rol FROM usuarios WHERE id = ?", (x_usuario_id,)).fetchone()
    finally:
        conn.close()
    if fila is None:
        raise HTTPException(status_code=401, detail=f"El usuario {x_usuario_id!r} no existe.")
    return dict(fila)


def requiere_rol(*roles: str, accion: str) -> Callable[..., dict]:
    """Dependencia: deja pasar solo a los roles indicados; `accion` se usa en el mensaje de 403."""

    def verificar(usuario: Annotated[dict, Depends(usuario_actual)]) -> dict:
        if usuario["rol"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Tu rol ({usuario['rol']}) no puede {accion}. Lo puede hacer: {', '.join(roles)}.",
            )
        return usuario

    return verificar


def conexion():
    """Una conexión por petición, cerrada al terminar."""
    conn: sqlite3.Connection = get_connection(entre_hilos=True)
    try:
        yield conn
    finally:
        conn.close()
