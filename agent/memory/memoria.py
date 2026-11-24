"""Memoria persistente, visible y editable (regla 5 de CLAUDE.md).

Cada hecho tiene texto, origen y fecha. Nada se aprende solo: un hecho nuevo entra «por confirmar» y solo los
hechos **activos y confirmados** se inyectan al contexto del modelo (decisión abierta 5: evitar contaminar la
memoria con cotizaciones malas). Módulo sin rutas HTTP; las rutas son del Hito 3.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

ESTADOS = ("Activa", "Pausada")
MAX_HECHOS_EN_CONTEXTO = 10


def _ahora() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def agregar(conn: sqlite3.Connection, texto: str, origen: str, confirmado: bool = False) -> int:
    texto = texto.strip()
    if not texto:
        raise ValueError("El hecho de memoria no puede estar vacío.")
    if not origen.strip():
        raise ValueError("Todo hecho de memoria necesita un origen.")
    cur = conn.execute(
        "INSERT INTO memoria (texto, origen, fecha, estado, por_confirmar) VALUES (?, ?, ?, 'Activa', ?)",
        (texto, origen.strip(), _ahora(), 0 if confirmado else 1),
    )
    conn.commit()
    return int(cur.lastrowid)


def listar(conn: sqlite3.Connection) -> list[dict]:
    return [dict(f) for f in conn.execute("SELECT * FROM memoria ORDER BY id DESC")]


def confirmar(conn: sqlite3.Connection, hecho_id: int) -> None:
    _existe(conn, hecho_id)
    conn.execute("UPDATE memoria SET por_confirmar = 0 WHERE id = ?", (hecho_id,))
    conn.commit()


def editar(conn: sqlite3.Connection, hecho_id: int, texto: str) -> None:
    """Corregir un hecho lo deja por confirmar de nuevo: una persona debe validar el texto nuevo."""
    texto = texto.strip()
    if not texto:
        raise ValueError("El hecho de memoria no puede estar vacío.")
    _existe(conn, hecho_id)
    conn.execute("UPDATE memoria SET texto = ?, por_confirmar = 1 WHERE id = ?", (texto, hecho_id))
    conn.commit()


def cambiar_estado(conn: sqlite3.Connection, hecho_id: int, estado: str) -> None:
    if estado not in ESTADOS:
        raise ValueError(f"Estado no válido: {estado!r}. Valores: {', '.join(ESTADOS)}.")
    _existe(conn, hecho_id)
    conn.execute("UPDATE memoria SET estado = ? WHERE id = ?", (estado, hecho_id))
    conn.commit()


def borrar(conn: sqlite3.Connection, hecho_id: int) -> None:
    _existe(conn, hecho_id)
    conn.execute("DELETE FROM memoria WHERE id = ?", (hecho_id,))
    conn.commit()


def para_contexto(conn: sqlite3.Connection) -> list[dict]:
    """Hechos que SÍ puede ver el modelo: activos y confirmados, los más recientes primero."""
    filas = conn.execute(
        "SELECT * FROM memoria WHERE estado = 'Activa' AND por_confirmar = 0 ORDER BY id DESC LIMIT ?",
        (MAX_HECHOS_EN_CONTEXTO,),
    )
    return [dict(f) for f in filas]


def _existe(conn: sqlite3.Connection, hecho_id: int) -> None:
    if conn.execute("SELECT 1 FROM memoria WHERE id = ?", (hecho_id,)).fetchone() is None:
        raise KeyError(f"No existe el hecho de memoria {hecho_id}.")
