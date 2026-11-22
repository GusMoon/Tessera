"""Módulo de conexión y operaciones base de SQLite para Tessera."""

import sqlite3
import os
from pathlib import Path
from typing import Generator

# Ruta predeterminada de la base de datos
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "tessera.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


def get_db_path() -> Path:
    """Devuelve la ruta absoluta al archivo SQLite."""
    return Path(os.environ.get("TESSERA_DB_PATH", str(DB_PATH)))


def get_connection() -> sqlite3.Connection:
    """Abre y configura una conexión SQLite con soporte de claves foráneas y filas como diccionarios."""
    db_file = get_db_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), timeout=15.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset: bool = False) -> None:
    """Inicializa las tablas ejecutando schema.sql. Si reset=True, borra la base antes."""
    db_file = get_db_path()
    if reset and db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            pass

    conn = get_connection()
    try:
        if reset:
            # En caso de que el archivo estuviera bloqueado para unlink, borramos tablas
            tablas = ["rechazos", "fichas_tecnicas", "partidas_historicas", 
                      "cotizaciones_historicas", "catalogo", "fuentes"]
            for t in tablas:
                conn.execute(f"DROP TABLE IF EXISTS {t};")
        
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Base de datos inicializada con éxito en {get_db_path()}")
