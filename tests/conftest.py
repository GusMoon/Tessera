"""Fixtures compartidas de las pruebas del Hito 2 (recuperación, intérprete, orquestador, e2e).

Usan el dataset sintético en una base temporal propia y el embedder por hashing: sin red, sin descargas, rápido.
La calidad con el modelo real (e5) se mide en `eval/evaluar.py`, no aquí.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Las pruebas nunca cargan el modelo real ni escriben en data/index/: el reindexado de la API usa hash y una carpeta temporal.
os.environ["TESSERA_EMBEDDER"] = "hash"
os.environ.setdefault("TESSERA_INDEX_DIR", tempfile.mkdtemp(prefix="tessera_idx_"))

SINTETICOS = Path(__file__).resolve().parents[1] / "data" / "synthetic"


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    """{'conn', 'indice', 'embedder'}: dataset sintético cargado e indexado en una base temporal."""
    mp = pytest.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp("h2")
    mp.setenv("TESSERA_DB_PATH", str(carpeta / "t.db"))
    mp.setenv("TESSERA_INDEX_DIR", str(carpeta / "indice"))

    from db.database import get_connection, init_db
    from ingest.servicio import procesar_archivo
    from retrieval.embeddings import EmbedderHash
    from retrieval.servicio import obtener_indice, olvidar_indice, reindexar

    olvidar_indice()
    init_db(reset=True)
    conn = get_connection()
    archivos = [SINTETICOS / "catalogo_materiales.csv", SINTETICOS / "historial_cotizaciones.xlsx",
                SINTETICOS / "tarifario_servicios.csv", *sorted((SINTETICOS / "fichas_tecnicas").glob("*.pdf"))]
    for a in archivos:
        procesar_archivo(a, a.name, conn=conn)
    conn.commit()
    embedder = EmbedderHash()
    reindexar(conn, embedder)
    yield {"conn": conn, "indice": obtener_indice(conn, embedder), "embedder": embedder}
    conn.close()
    olvidar_indice()
    mp.undo()
