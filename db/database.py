"""Módulo de conexión y operaciones base de SQLite para Tessera."""

import sqlite3
import os
from pathlib import Path

# Ruta predeterminada de la base de datos
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "tessera.db"
SCHEMA_PATH = DB_DIR / "schema.sql"

# Tablas que se llenan al cargar fuentes (se vacían con `vaciar_ingesta`). Hijas primero.
TABLAS_INGESTA = [
    "fragmentos_fts", "fragmentos", "rechazos", "fichas_tecnicas", "partidas_historicas",
    "cotizaciones_historicas", "catalogo", "servicios", "fuentes",
]
# Tablas de trabajo del usuario (cotizaciones, aprobaciones, memoria, bitácora). Hijas primero.
TABLAS_TRABAJO = [
    "aprobaciones", "cotizacion_historial", "cotizacion_partidas", "cotizacion_escenarios",
    "cotizaciones", "memoria", "bitacora", "usuarios",
]

# Usuarios de prueba (el prototipo no autentica: la identidad llega en la cabecera X-Usuario-Id).
USUARIOS_PRUEBA = [
    ("u1", "Ana Pérez", "Vendedor"),
    ("u2", "Marcos Díaz", "Responsable comercial"),
    ("u3", "Laura Canché", "Administrador"),
]


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


def _columnas(conn: sqlite3.Connection, tabla: str) -> set[str]:
    return {fila["name"] for fila in conn.execute(f"PRAGMA table_info({tabla})")}


def _migrar(conn: sqlite3.Connection) -> None:
    """Agrega a bases ya existentes las columnas nuevas (`CREATE TABLE IF NOT EXISTS` no las agrega)."""
    if "permiso" not in _columnas(conn, "fuentes"):
        conn.execute("ALTER TABLE fuentes ADD COLUMN permiso TEXT NOT NULL DEFAULT 'Todos'")


def _sembrar_usuarios(conn: sqlite3.Connection) -> None:
    conn.executemany("INSERT OR IGNORE INTO usuarios (id, nombre, rol) VALUES (?, ?, ?)", USUARIOS_PRUEBA)


def _borrar_tablas(conn: sqlite3.Connection, tablas: list[str]) -> None:
    for t in tablas:
        conn.execute(f"DROP TABLE IF EXISTS {t};")


def init_db(reset: bool = False) -> None:
    """Inicializa las tablas ejecutando schema.sql. Si reset=True, borra la base antes (todo, incluidas
    cotizaciones, memoria y bitácora)."""
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
            _borrar_tablas(conn, TABLAS_TRABAJO + TABLAS_INGESTA)

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        _migrar(conn)
        _sembrar_usuarios(conn)
        conn.commit()
    finally:
        conn.close()


def vaciar_ingesta() -> None:
    """Vacía solo lo cargado desde «Fuentes» (y su índice). Conserva usuarios, cotizaciones, memoria y bitácora:
    las partidas de una cotización guardan su propia copia de la fuente, así que no quedan huérfanas."""
    conn = get_connection()
    try:
        _borrar_tablas(conn, TABLAS_INGESTA)
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        _migrar(conn)
        _sembrar_usuarios(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Base de datos inicializada con éxito en {get_db_path()}")
