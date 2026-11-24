"""Pruebas de la Fase 1: tarifario de servicios, permisos por fuente, esquema ampliado y migración.

Cada prueba usa su propia base SQLite temporal (TESSERA_DB_PATH): no toca db/tessera.db.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db.database import get_connection, init_db, vaciar_ingesta
from ingest.servicio import procesar_archivo

SINTETICOS = Path(__file__).resolve().parents[2] / "data" / "synthetic"


@pytest.fixture
def bd(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_DB_PATH", str(tmp_path / "prueba.db"))
    init_db(reset=True)
    return tmp_path / "prueba.db"


def contar(tabla: str) -> int:
    conn = get_connection()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
    finally:
        conn.close()


def cargar_dataset() -> list[dict]:
    archivos = [SINTETICOS / "catalogo_materiales.csv", SINTETICOS / "historial_cotizaciones.xlsx",
                SINTETICOS / "tarifario_servicios.csv", *sorted((SINTETICOS / "fichas_tecnicas").glob("*.pdf"))]
    return [procesar_archivo(a, a.name) for a in archivos]


def test_dataset_completo_cumple_el_manifiesto(bd):
    manifiesto = json.loads((SINTETICOS / "manifiesto.json").read_text(encoding="utf-8"))["resumen"]
    resultados = cargar_dataset()
    assert len(resultados) == manifiesto["total_archivos"] == 13
    assert contar("catalogo") == manifiesto["catalogo_csv"]["filas_validas"] == 47
    assert contar("partidas_historicas") == manifiesto["historial_xlsx"]["filas_validas"] == 115
    assert contar("fichas_tecnicas") == manifiesto["fichas_pdf"]["validos"] == 10
    assert contar("servicios") == manifiesto["tarifario_servicios"]["filas_validas"] == 15
    assert contar("rechazos") == manifiesto["totales_combinados"]["total_filas_defectuosas"] == 8
    assert all(r["estado"] == "Listo" for r in resultados)


def test_el_tarifario_no_se_confunde_con_el_catalogo(bd):
    r = procesar_archivo(SINTETICOS / "tarifario_servicios.csv", "tarifario_servicios.csv")
    assert r["tipo"] == "CSV" and r["guardadas"] == 15 and r["rechazadas"] == 0
    assert contar("servicios") == 15 and contar("catalogo") == 0


def test_servicios_marca_precios_antiguos_y_opcionales(bd):
    procesar_archivo(SINTETICOS / "tarifario_servicios.csv", "tarifario_servicios.csv")
    conn = get_connection()
    try:
        antiguos = {f["codigo"] for f in conn.execute("SELECT codigo FROM servicios WHERE desactualizado = 1")}
        premium = {f["codigo"] for f in conn.execute("SELECT codigo FROM servicios WHERE incluir_en = 'premium'")}
    finally:
        conn.close()
    assert antiguos == {"SRV-FLE-MOT", "SRV-FLE-VAL", "SRV-INS-LUM"}
    assert premium == {"SRV-OPC-SUP", "SRV-OPC-GAR"}


def test_filas_defectuosas_del_tarifario_se_rechazan_con_motivo(bd):
    csv_sucio = (
        "Codigo,Servicio,Tipo,Unidad,Precio_Unitario,Zona,Incluir_En,Fecha_Precio,Notas\n"
        "SRV-OK,Flete bueno,Flete,viaje,$500.00 MXN,Mérida,todos,01/11/2026,\n"
        ",Sin código,Flete,viaje,100,,todos,01/11/2026,\n"
        "SRV-T,Tipo raro,Magia,viaje,100,,todos,01/11/2026,\n"
        "SRV-P,Precio malo,Flete,viaje,CONSULTAR,,todos,01/11/2026,\n"
        "SRV-I,Incluir raro,Flete,viaje,100,,nunca,01/11/2026,\n"
    ).encode("utf-8")
    r = procesar_archivo(csv_sucio, "sucio.csv")
    assert (r["leidas"], r["guardadas"], r["rechazadas"]) == (5, 1, 4)
    conn = get_connection()
    try:
        motivos = {f["campo"]: f["motivo"] for f in conn.execute("SELECT campo, motivo FROM rechazos")}
    finally:
        conn.close()
    assert motivos["Codigo"] == "Código de servicio faltante o vacío"
    assert motivos["Tipo"] == "Tipo de servicio no reconocido"
    assert motivos["Precio_Unitario"] == "Precio no numérico o vacío"
    assert motivos["Incluir_En"] == "Valor de Incluir_En no reconocido"


def test_permisos_predeterminados_por_tipo_de_fuente(bd):
    cargar_dataset()
    conn = get_connection()
    try:
        permisos = {f["nombre"]: f["permiso"] for f in conn.execute("SELECT nombre, permiso FROM fuentes")}
    finally:
        conn.close()
    assert permisos["catalogo_materiales.csv"] == "Todos"
    assert permisos["historial_cotizaciones.xlsx"] == "Comercial"
    assert permisos["tarifario_servicios.csv"] == "Comercial"
    assert permisos["ficha_01_gabinete_nema4x.pdf"] == "Todos"


def test_permiso_explicito_y_validacion(bd):
    r = procesar_archivo(SINTETICOS / "catalogo_materiales.csv", "catalogo_materiales.csv", permiso="Administración")
    assert r["permiso"] == "Administración"
    with pytest.raises(ValueError, match="Permiso no válido"):
        procesar_archivo(SINTETICOS / "catalogo_materiales.csv", "otro.csv", permiso="Secreto")


def test_reprocesar_reemplaza_sin_duplicar(bd):
    for _ in range(2):
        procesar_archivo(SINTETICOS / "tarifario_servicios.csv", "tarifario_servicios.csv")
    assert contar("servicios") == 15 and contar("fuentes") == 1


def test_usuarios_de_prueba_sembrados(bd):
    conn = get_connection()
    try:
        roles = {f["id"]: f["rol"] for f in conn.execute("SELECT id, rol FROM usuarios")}
    finally:
        conn.close()
    assert roles == {"u1": "Vendedor", "u2": "Responsable comercial", "u3": "Administrador"}


def test_migracion_agrega_permiso_a_una_base_vieja(tmp_path, monkeypatch):
    vieja = tmp_path / "vieja.db"
    conn = sqlite3.connect(vieja)
    conn.execute("CREATE TABLE fuentes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL, tipo TEXT NOT NULL,"
                 " hash_archivo TEXT, tamano_bytes INTEGER DEFAULT 0, estado TEXT NOT NULL DEFAULT 'Procesando',"
                 " filas_leidas INTEGER DEFAULT 0, filas_guardadas INTEGER DEFAULT 0, filas_rechazadas INTEGER DEFAULT 0,"
                 " filas_omitidas INTEGER DEFAULT 0, motivo TEXT, fecha_carga TEXT NOT NULL)")
    conn.execute("INSERT INTO fuentes (nombre, tipo, fecha_carga) VALUES ('viejo.csv', 'CSV', '2026-01-01')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("TESSERA_DB_PATH", str(vieja))
    init_db(reset=False)
    conn = get_connection()
    try:
        assert conn.execute("SELECT permiso FROM fuentes WHERE nombre = 'viejo.csv'").fetchone()[0] == "Todos"
    finally:
        conn.close()


def test_vaciar_ingesta_conserva_el_trabajo_del_usuario(bd):
    cargar_dataset()
    conn = get_connection()
    conn.execute("INSERT INTO memoria (texto, origen, fecha) VALUES ('hecho', 'prueba', '2026-11-21')")
    conn.execute("INSERT INTO cotizaciones (folio, cliente, solicitud, creada_por, fecha) VALUES ('COT-1', 'X', 'pide', 'u1', '2026-11-21T10:00')")
    conn.commit()
    conn.close()
    vaciar_ingesta()
    assert contar("fuentes") == contar("catalogo") == contar("servicios") == 0
    assert contar("memoria") == 1 and contar("cotizaciones") == 1 and contar("usuarios") == 3


# --------------------------------------------------------------------------- API de fuentes
def test_api_fuentes_expone_y_acepta_permiso(bd):
    cliente = TestClient(app)  # sin `with`: no corre el arranque; la base ya la preparó el fixture
    datos = (SINTETICOS / "catalogo_materiales.csv").read_bytes()
    r = cliente.post("/api/fuentes/subir", files={"file": ("catalogo.csv", datos, "text/csv")}, data={"permiso": "Comercial"})
    assert r.status_code == 200 and r.json()["fuente"]["permiso"] == "Comercial"
    assert cliente.get("/api/fuentes").json()[0]["permiso"] == "Comercial"
    malo = cliente.post("/api/fuentes/subir", files={"file": ("x.csv", datos, "text/csv")}, data={"permiso": "Secreto"})
    assert malo.status_code == 400


def test_api_cargar_dataset_incluye_tarifario_y_limpiar_conserva_usuarios(bd):
    cliente = TestClient(app)
    r = cliente.post("/api/fuentes/cargar-dataset-sintetico")
    assert r.status_code == 200 and r.json()["archivos_procesados"] == 13
    assert cliente.post("/api/fuentes/limpiar").status_code == 200
    assert cliente.get("/api/fuentes").json() == [] and contar("usuarios") == 3
