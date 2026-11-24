"""Reindexa la base actual (fragmentos + FTS5 + vectores) e imprime los tiempos medidos.

    python scripts/indexar.py                  # usa TESSERA_EMBEDDER (e5 por defecto)
    python scripts/indexar.py --embedder hash  # sin descargas, solo para pruebas
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import get_connection, get_db_path, init_db  # noqa: E402
from retrieval.embeddings import crear_embedder  # noqa: E402
from retrieval.servicio import carpeta_indice, reindexar  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--embedder", choices=["e5", "hash"], default=None)
    args = ap.parse_args()
    init_db()
    print(f"Base: {get_db_path()}")
    conn = get_connection()
    try:
        if conn.execute("SELECT COUNT(*) FROM fuentes").fetchone()[0] == 0:
            print("No hay fuentes cargadas. Carga el dataset desde «Fuentes» o con verificar_ingesta.py.")
            return 1
        r = reindexar(conn, crear_embedder(args.embedder))
    finally:
        conn.close()
    print(f"Fragmentos: {r['fragmentos']} · embedder: {r['embedder']}")
    print(f"Fragmentos y FTS5: {r['segundos_fragmentos']} s · vectores: {r['segundos_vectores']} s")
    print(f"Índice guardado en {carpeta_indice()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
