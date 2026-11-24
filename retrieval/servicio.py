"""Punto de entrada para reindexar y para obtener el índice de la base en uso."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

from db.database import get_connection, get_db_path
from retrieval.embeddings import Embedder, crear_embedder
from retrieval.fragmentos import construir_fragmentos
from retrieval.indice import Indice

RAIZ = Path(__file__).resolve().parents[1]
_cache: dict[str, Indice] = {}
_embedder: Embedder | None = None
_candado_embedder = threading.Lock()  # la precarga al arrancar y la primera cotización no deben cargar el modelo dos veces


def carpeta_indice() -> Path:
    """`data/index/` por defecto; `TESSERA_INDEX_DIR` la cambia (las pruebas usan una temporal)."""
    return Path(os.environ.get("TESSERA_INDEX_DIR") or RAIZ / "data" / "index")


def obtener_embedder() -> Embedder:
    """El modelo se carga una sola vez por proceso."""
    global _embedder
    with _candado_embedder:
        if _embedder is None:
            _embedder = crear_embedder()
        return _embedder


def reindexar(conn: sqlite3.Connection | None = None, embedder: Embedder | None = None) -> dict:
    """Reconstruye fragmentos, FTS5 y vectores de la base actual. Devuelve conteos y tiempos medidos."""
    propia = conn is None
    conn = conn or get_connection()
    try:
        emb = embedder or obtener_embedder()
        t0 = time.perf_counter()
        n = construir_fragmentos(conn)
        t1 = time.perf_counter()
        indice = Indice.construir(conn, emb)
        t2 = time.perf_counter()
        indice.guardar(carpeta_indice())
        _cache[str(get_db_path())] = indice
        return {
            "fragmentos": n,
            "embedder": emb.nombre,
            "segundos_fragmentos": round(t1 - t0, 3),
            "segundos_vectores": round(t2 - t1, 3),
        }
    finally:
        if propia:
            conn.close()


def obtener_indice(conn: sqlite3.Connection, embedder: Embedder | None = None) -> Indice:
    """Índice de la base en uso: en memoria, o del disco si sigue vigente, o se reconstruye."""
    clave = str(get_db_path())
    if clave in _cache:
        return _cache[clave]
    emb = embedder or obtener_embedder()
    indice = Indice.cargar(carpeta_indice(), emb, conn)
    if indice is None:
        reindexar(conn, emb)
        return _cache[clave]
    _cache[clave] = indice
    return indice


def olvidar_indice() -> None:
    """Descarta el índice en memoria (tras vaciar las fuentes o cambiar de base)."""
    _cache.clear()
