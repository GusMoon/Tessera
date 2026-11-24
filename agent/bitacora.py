"""Bitácora de auditoría: qué se preguntó, qué fuentes y herramientas se usaron y cuánto tardó.

No guarda texto del modelo ni claves. Módulo sin rutas HTTP; las rutas son del Hito 3.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime


def registrar(
    conn: sqlite3.Connection,
    usuario: str,
    pregunta: str,
    documentos: list[str],
    herramientas: list[str],
    duracion_ms: int,
    cotizacion: str | None = None,
    aprobado_por: str | None = None,
) -> int:
    fila = conn.execute("SELECT nombre FROM usuarios WHERE id = ?", (usuario,)).fetchone()
    usuario = fila["nombre"] if fila else usuario  # admite el id de usuario o un nombre ya resuelto
    cur = conn.execute(
        """INSERT INTO bitacora (fecha, usuario, pregunta, documentos_json, herramientas_json, duracion_ms, cotizacion, aprobado_por)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().replace(microsecond=0).isoformat(), usuario, pregunta, json.dumps(documentos, ensure_ascii=False),
         json.dumps(herramientas, ensure_ascii=False), int(duracion_ms), cotizacion, aprobado_por),
    )
    conn.commit()
    return int(cur.lastrowid)


def listar(conn: sqlite3.Connection, limite: int = 100) -> list[dict]:
    filas = conn.execute("SELECT * FROM bitacora ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    salida = []
    for f in filas:
        d = dict(f)
        d["documentos"] = json.loads(d.pop("documentos_json"))
        d["herramientas"] = json.loads(d.pop("herramientas_json"))
        salida.append(d)
    return salida
