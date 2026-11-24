"""Herramienta `buscar_precios`: artículos del catálogo y servicios del tarifario, con precio, fecha y fuente.

La búsqueda ya filtra por permisos del usuario antes de recuperar (`retrieval.Indice.buscar`); aquí solo se
completa cada resultado con su precio exacto leído de SQLite, nunca del texto del fragmento.
"""

from __future__ import annotations

import sqlite3
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from retrieval.indice import Indice


def a_centavos(precio) -> int:
    """Pesos (REAL de SQLite) a centavos enteros, sin errores de punto flotante."""
    return int((Decimal(str(precio)) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def buscar_precios(
    conn: sqlite3.Connection,
    indice: Indice,
    consulta: str,
    usuario_id: str,
    k: int = 5,
    tipos: tuple[str, ...] = ("catalogo", "servicio"),
    vector: np.ndarray | None = None,
) -> list[dict]:
    resultados = []
    for r in indice.buscar(conn, consulta, usuario_id, k=k, tipos=tipos, vector=vector):
        f = r.fragmento
        codigo = f.ref.split(":", 1)[1]
        if f.tipo == "catalogo":
            fila = conn.execute(
                "SELECT descripcion, unidad, precio_unitario, fecha_precio, antiguedad_meses, categoria FROM catalogo WHERE sku = ? AND fuente_id = ?",
                (codigo, f.fuente_id),
            ).fetchone()
            if fila is None:
                continue
            item = {"concepto": fila["descripcion"], "unidad": fila["unidad"], "categoria": fila["categoria"],
                    "precio_centavos": a_centavos(fila["precio_unitario"]), "fecha": fila["fecha_precio"],
                    "antiguedad_meses": fila["antiguedad_meses"] or 0, "tipo_servicio": None, "zona": None, "incluir_en": "todos"}
        else:
            fila = conn.execute(
                "SELECT servicio, unidad, precio_unitario, fecha_precio, antiguedad_meses, tipo, zona, incluir_en FROM servicios WHERE codigo = ? AND fuente_id = ?",
                (codigo, f.fuente_id),
            ).fetchone()
            if fila is None:
                continue
            item = {"concepto": fila["servicio"], "unidad": fila["unidad"], "categoria": None,
                    "precio_centavos": a_centavos(fila["precio_unitario"]), "fecha": fila["fecha_precio"],
                    "antiguedad_meses": fila["antiguedad_meses"] or 0, "tipo_servicio": fila["tipo"], "zona": fila["zona"],
                    "incluir_en": fila["incluir_en"]}
        resultados.append({"ref": f.ref, "tipo": f.tipo, "codigo": codigo, "puntaje": r.puntaje, "rangos": r.rangos, **item})
    return resultados
