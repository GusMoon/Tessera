"""Extremo a extremo del Hito 2: cargar fuentes por la API → indexar → pedir una cotización → 3 escenarios con fuentes.

Usa el embedder por hashing (sin descargas). Con el modelo real, el veredicto sale de `python eval/evaluar.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.cotizar import cotizar
from eval import referencia

RAIZ = Path(__file__).resolve().parents[2]
CASOS = json.loads((RAIZ / "data" / "eval" / "casos.json").read_text(encoding="utf-8"))["casos"]


@pytest.fixture(scope="module")
def sistema(tmp_path_factory):
    """Base vacía → /api/fuentes/cargar-dataset-sintetico (que reindexa en segundo plano) → índice listo."""
    mp = pytest.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp("e2e")
    mp.setenv("TESSERA_DB_PATH", str(carpeta / "e2e.db"))
    mp.setenv("TESSERA_INDEX_DIR", str(carpeta / "indice"))
    from api.main import app
    from db.database import get_connection, init_db
    from retrieval.servicio import obtener_indice, olvidar_indice

    olvidar_indice()
    init_db(reset=True)
    with TestClient(app, headers={"X-Usuario-Id": "u3"}) as cliente:
        r = cliente.post("/api/fuentes/cargar-dataset-sintetico")
        assert r.status_code == 200 and r.json()["archivos_procesados"] == 13
        assert (carpeta / "indice" / "meta.json").exists()  # el reindexado se disparó solo tras la carga
        conn = get_connection()
        yield {"conn": conn, "indice": obtener_indice(conn), "cliente": cliente}
        conn.close()
    olvidar_indice()
    mp.undo()


def test_cargar_las_fuentes_deja_el_indice_listo(sistema):
    n = sistema["conn"].execute("SELECT COUNT(*) FROM fragmentos").fetchone()[0]
    assert n == len(sistema["indice"].ids) >= 105


def test_flujo_completo_de_una_solicitud(sistema):
    r = cotizar("Necesito 20 gabinetes NEMA 4X 40x30x20 y 100 rollos de cable THW calibre 12 negro, con instalación y flete a Umán",
                "u1", sistema["conn"], sistema["indice"])
    assert r["estado"] == "completa" and list(r["escenarios"]) == ["economico", "recomendado", "premium"]
    totales = [r["escenarios"][e]["total_centavos"] for e in r["escenarios"]]
    assert totales == sorted(totales) and len(set(totales)) == 3
    refs = {f["ref"] for f in r["fuentes"]}
    assert {"catalogo:GAB-403020", "catalogo:CAB-THW-12N", "servicio:SRV-INS-GAB", "servicio:SRV-FLE-UMA"} <= refs
    assert any(f["ref"].startswith("historial:") for f in r["fuentes"])  # cotizaciones parecidas citadas
    assert r["tiempos_ms"]["total"] < 500


def test_los_50_casos_con_el_embedder_de_respaldo(sistema):
    exactos = top5 = con_fuentes = 0
    for caso in CASOS:
        r = cotizar(caso["solicitud"], "u1", sistema["conn"], sistema["indice"])
        assert r["estado"] == "completa", (caso["id"], r["preguntas"])
        esperado = caso["esperado"]
        exactos += all({k: r["escenarios"][e][k] for k in ("subtotal_centavos", "iva_centavos", "total_centavos")} == esperado[e] for e in esperado)
        top5 += caso["folio_parecido"] in [h["folio"] for h in r["historial_parecido"]]
        con_fuentes += bool(r["fuentes"]) and all(p["fuente_ref"] for e in r["escenarios"].values() for p in e["partidas"])
    assert exactos == len(CASOS) and con_fuentes == len(CASOS) and top5 / len(CASOS) >= 0.8


def test_los_totales_esperados_del_archivo_coinciden_con_la_referencia_independiente():
    assert len(CASOS) == 50
    for caso in CASOS:
        assert caso["esperado"] == referencia.totales_esperados(caso["renglones"], caso["servicios"]), caso["id"]


def test_los_casos_estan_repartidos_entre_las_cinco_personas():
    por_autor = {}
    for c in CASOS:
        por_autor[c["autor"]] = por_autor.get(c["autor"], 0) + 1
    assert por_autor == {"Gustavo": 10, "Jorge": 10, "Erick": 10, "Anyeli": 10, "Jhoana": 10}
    assert len({c["id"] for c in CASOS}) == 50


def test_un_vendedor_no_recibe_fuentes_de_administracion(sistema):
    c, indice = sistema["conn"], sistema["indice"]
    c.execute("UPDATE fuentes SET permiso = 'Administración' WHERE nombre = 'tarifario_servicios.csv'")
    c.commit()
    from retrieval.fragmentos import construir_fragmentos
    from retrieval.indice import Indice

    construir_fragmentos(c)
    restringido = Indice.construir(c, indice.embedder)
    r = cotizar("20 gabinetes NEMA 4X con instalación y flete a Umán", "u1", c, restringido)
    assert not [l for l in r["fuentes"] if l["ref"].startswith("servicio:")]  # sin tarifario visible no se inventan servicios
    r = cotizar("20 gabinetes NEMA 4X con instalación y flete a Umán", "u3", c, restringido)
    assert any(l["ref"] == "servicio:SRV-FLE-UMA" for l in r["fuentes"])
    c.execute("UPDATE fuentes SET permiso = 'Comercial' WHERE nombre = 'tarifario_servicios.csv'")
    c.commit()
