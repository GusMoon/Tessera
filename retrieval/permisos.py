"""Qué fuentes puede abrir cada usuario (regla 6 de CLAUDE.md: se filtra ANTES de recuperar).

Prototipo: la identidad es el id de la tabla `usuarios`, sin autenticación real. La matriz es una propuesta
que debe validar la Persona E (decisiones abiertas 1 y 6).
"""

from __future__ import annotations

import sqlite3

PERMISOS_POR_ROL: dict[str, frozenset[str]] = {
    "Vendedor": frozenset({"Todos", "Comercial"}),
    "Responsable comercial": frozenset({"Todos", "Comercial"}),
    "Administrador": frozenset({"Todos", "Comercial", "Administración"}),
}
SOLO_PUBLICO = frozenset({"Todos"})


def permisos_de(usuario_id: str, conn: sqlite3.Connection) -> frozenset[str]:
    """Permisos de fuente del usuario. Un usuario inexistente solo ve lo público: ante la duda, lo mínimo."""
    fila = conn.execute("SELECT rol FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if fila is None:
        return SOLO_PUBLICO
    return PERMISOS_POR_ROL.get(fila[0], SOLO_PUBLICO)
