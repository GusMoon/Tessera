"""Contexto que se le entrega al modelo de conversación: qué fuentes hay cargadas y cómo se cotiza.

El modelo no ve las tablas, pero el sistema sí las consulta al cotizar. Sin este texto el modelo contesta «no tengo acceso a
ningún archivo» aunque haya un catálogo cargado. Solo cuenta lo que el usuario puede abrir (regla 6): una fuente
restringida no se menciona. Los números son conteos de filas, nunca precios (regla 1).
"""

from __future__ import annotations

import sqlite3

from retrieval.permisos import permisos_de

_TABLAS = (
    ("catalogo", "catálogo de materiales", "artículos"),
    ("servicios", "tarifario de servicios (fletes, instalación, opcionales)", "servicios"),
    ("cotizaciones_historicas", "historial de cotizaciones", "cotizaciones"),
    ("fichas_tecnicas", "fichas técnicas en PDF", "fichas"),
)

CIERRE = (
    "El sistema, no tú, calcula las cotizaciones: cuando el usuario escribe materiales con cantidades, o adjunta la solicitud "
    "(PDF, Excel, CSV o texto de chat) con el clip, el sistema las busca en estas fuentes y arma tres escenarios con importes "
    "calculados por código. No digas que no tienes acceso a las fuentes ni pidas que las vuelva a subir: explica cómo pedir la "
    "cotización (materiales con cantidades, o adjuntar la solicitud). No inventes precios ni cantidades."
)


def describir_fuentes(conn: sqlite3.Connection, usuario_id: str) -> str:
    """Texto para el prompt de sistema con lo cargado y visible para el usuario."""
    permisos = sorted(permisos_de(usuario_id, conn))
    marcas = ",".join("?" for _ in permisos)
    partes = []
    for tabla, nombre, plural in _TABLAS:
        n = conn.execute(
            f"SELECT COUNT(*) FROM {tabla} t JOIN fuentes f ON f.id = t.fuente_id WHERE f.permiso IN ({marcas})", permisos  # noqa: S608
        ).fetchone()[0]
        if n:
            partes.append(f"{nombre}: {n} {plural}")
    if not partes:
        return "Aún no hay fuentes cargadas: un Administrador debe cargarlas en la pantalla Fuentes antes de cotizar."
    return "Fuentes cargadas que este usuario puede usar: " + "; ".join(partes) + ".\n" + _ejemplos(conn, permisos, marcas) + CIERRE


def _ejemplos(conn: sqlite3.Connection, permisos: list[str], marcas: str) -> str:
    """Tres artículos reales de categorías distintas, para que los ejemplos del modelo salgan del catálogo y no inventados."""
    filas = conn.execute(
        f"SELECT c.categoria, MIN(c.descripcion) FROM catalogo c JOIN fuentes f ON f.id = c.fuente_id "  # noqa: S608
        f"WHERE f.permiso IN ({marcas}) AND c.categoria IS NOT NULL GROUP BY c.categoria ORDER BY c.categoria LIMIT 3",
        permisos,
    ).fetchall()
    if not filas:
        return ""
    return (
        "Ejemplos reales del catálogo (si das un ejemplo de solicitud, usa materiales como estos y nunca inventes otros, como ladrillo o "
        "cemento, que no estén en las fuentes): " + "; ".join(f"«{f[1]}»" for f in filas) + ".\n"
    )
