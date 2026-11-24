"""Herramienta `buscar_historial`: cotizaciones históricas parecidas a una solicitud, con cliente, fecha y fuente."""

from __future__ import annotations

import sqlite3

import numpy as np

from retrieval.indice import Indice


def buscar_historial(
    conn: sqlite3.Connection,
    indice: Indice,
    consulta: str,
    usuario_id: str,
    k: int = 5,
    desde: str | None = None,
    vector: np.ndarray | None = None,
) -> list[dict]:
    """Folios históricos parecidos (solo de fuentes que el usuario puede abrir). `desde` descarta los más viejos."""
    salida = []
    for r in indice.buscar(conn, consulta, usuario_id, k=k, tipos=("historial",), desde=desde, vector=vector):
        f = r.fragmento
        folio = f.ref.split(":", 1)[1]
        cab = conn.execute(
            "SELECT cliente, fecha, desactualizado FROM cotizaciones_historicas WHERE folio = ? AND fuente_id = ?",
            (folio, f.fuente_id),
        ).fetchone()
        salida.append(
            {
                "ref": f.ref,
                "folio": folio,
                "cliente": cab["cliente"] if cab else None,
                "fecha": cab["fecha"] if cab else f.fecha,
                "desactualizado": bool(cab["desactualizado"]) if cab else False,
                "resumen": f.texto,
                "puntaje": r.puntaje,
                "rangos": r.rangos,
            }
        )
    return salida
