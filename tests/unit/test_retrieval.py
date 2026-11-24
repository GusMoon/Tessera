"""Recuperación híbrida: permisos y fecha se filtran ANTES de buscar (regla 6), RRF, persistencia y embedder de respaldo."""

from __future__ import annotations

import numpy as np
import pytest

from ingest.servicio import procesar_archivo
from retrieval import Indice, permisos_de
from retrieval.embeddings import EmbedderHash, crear_embedder, normalizar_texto
from retrieval.fragmentos import _trozos, construir_fragmentos
from retrieval.indice import K_RRF, tokens_busqueda
from retrieval.servicio import reindexar

CSV_ADMIN = (
    "SKU,Descripcion,Categoria,Unidad,Precio_Unitario,Moneda,Fecha_Precio,Notas\n"
    "ADM-GAB-SECRETO,Gabinete metálico NEMA 4X intemperie 40x30x20 cm costo interno confidencial,Gabinetes,pza,$100.00 MXN,MXN,2026-11-01,Solo administración\n"
).encode("utf-8")


def refs(resultados):
    return [r.fragmento.ref for r in resultados]


# --------------------------------------------------------------------------- fragmentos y permisos
def test_fragmentos_de_los_cuatro_tipos_con_ref_y_permiso(dataset):
    filas = dataset["conn"].execute("SELECT tipo, COUNT(*) n FROM fragmentos GROUP BY tipo").fetchall()
    por_tipo = {f["tipo"]: f["n"] for f in filas}
    assert por_tipo["catalogo"] == 47 and por_tipo["servicio"] == 15 and por_tipo["historial"] == 28 and por_tipo["ficha"] >= 10
    ref, permiso = dataset["conn"].execute("SELECT ref, permiso FROM fragmentos WHERE ref = 'historial:COT-MID-0101'").fetchone()
    assert ref == "historial:COT-MID-0101" and permiso == "Comercial"  # hereda el permiso de su fuente


def test_permisos_por_rol(dataset):
    c = dataset["conn"]
    assert permisos_de("u1", c) == {"Todos", "Comercial"}
    assert permisos_de("u2", c) == {"Todos", "Comercial"}
    assert permisos_de("u3", c) == {"Todos", "Comercial", "Administración"}
    assert permisos_de("no-existe", c) == {"Todos"}  # ante la duda, lo mínimo


def test_un_usuario_sin_permiso_nunca_recibe_la_fuente_aunque_sea_el_mejor_resultado(dataset):
    c, emb = dataset["conn"], dataset["embedder"]
    procesar_archivo(CSV_ADMIN, "costos_internos.csv", conn=c, permiso="Administración")
    c.commit()
    construir_fragmentos(c)  # reconstruye los fragmentos con la fuente nueva
    indice = Indice.construir(c, emb)
    consulta = "Gabinete metálico NEMA 4X intemperie 40x30x20 cm costo interno confidencial"
    visibles_vendedor = refs(indice.buscar(c, consulta, "u1", k=20))
    visibles_admin = refs(indice.buscar(c, consulta, "u3", k=20))
    assert "catalogo:ADM-GAB-SECRETO" not in visibles_vendedor
    assert visibles_admin[0] == "catalogo:ADM-GAB-SECRETO"  # sí es el mejor resultado para quien tiene permiso
    # Y se limpia para no afectar a las demás pruebas del módulo.
    c.execute("DELETE FROM catalogo WHERE sku = 'ADM-GAB-SECRETO'")
    c.execute("DELETE FROM fuentes WHERE nombre = 'costos_internos.csv'")
    c.commit()
    construir_fragmentos(c)
    dataset["indice"] = Indice.construir(c, emb)


def test_usuario_inexistente_solo_ve_fuentes_publicas(dataset):
    r = dataset["indice"].buscar(dataset["conn"], "cotización cliente gabinete", "fantasma", k=20)
    assert r and all(x.fragmento.permiso == "Todos" for x in r)


# --------------------------------------------------------------------------- filtros previos
def test_filtro_por_tipo(dataset):
    r = dataset["indice"].buscar(dataset["conn"], "tubo conduit", "u1", k=10, tipos=("servicio",))
    assert r and all(x.fragmento.tipo == "servicio" for x in r)


def test_el_filtro_de_fecha_excluye_antes_de_buscar(dataset):
    c, indice = dataset["conn"], dataset["indice"]
    todos = indice.buscar(c, "gabinete NEMA", "u1", k=50, tipos=("historial",))
    recientes = indice.buscar(c, "gabinete NEMA", "u1", k=50, tipos=("historial",), desde="2026-08-01")
    assert len(recientes) < len(todos)
    assert all(x.fragmento.fecha >= "2026-08-01" for x in recientes)


def test_consulta_sin_resultados_permitidos_devuelve_lista_vacia(dataset):
    assert dataset["indice"].buscar(dataset["conn"], "gabinete", "u1", tipos=("servicio",), desde="2099-01-01") == []


# --------------------------------------------------------------------------- fusión
def test_rrf_suma_ambas_listas_y_se_ordena_por_puntaje(dataset):
    r = dataset["indice"].buscar(dataset["conn"], "Gabinete metálico NEMA 4X intemperie", "u1", k=5, tipos=("catalogo",))
    assert r[0].fragmento.ref == "catalogo:GAB-403020"
    assert set(r[0].rangos) == {"bm25", "vector"}
    assert r[0].puntaje == pytest.approx(1 / (K_RRF + r[0].rangos["bm25"]) + 1 / (K_RRF + r[0].rangos["vector"]))
    assert [x.puntaje for x in r] == sorted((x.puntaje for x in r), reverse=True)


def test_la_busqueda_encuentra_por_palabras_exactas_y_por_significado(dataset):
    c, indice = dataset["conn"], dataset["indice"]
    assert refs(indice.buscar(c, "QO230", "u1", k=3))[0] == "catalogo:INT-TM-230"  # código exacto: lo aporta BM25


def test_tokens_de_busqueda_sin_acentos_ni_palabras_vacias():
    assert tokens_busqueda("Interruptor termomagnético de 3/4 para la obra") == ["interruptor", "termomagnetico", "3", "4", "obra"]


# --------------------------------------------------------------------------- índice
def test_guardar_y_cargar_el_indice(dataset, tmp_path):
    c, indice, emb = dataset["conn"], dataset["indice"], dataset["embedder"]
    indice.guardar(tmp_path)
    cargado = Indice.cargar(tmp_path, emb, c)
    assert cargado is not None and np.array_equal(cargado.ids, indice.ids)
    assert refs(cargado.buscar(c, "cable calibre 12", "u1")) == refs(indice.buscar(c, "cable calibre 12", "u1"))


def test_un_indice_viejo_se_descarta(dataset, tmp_path):
    c, indice, emb = dataset["conn"], dataset["indice"], dataset["embedder"]
    indice.guardar(tmp_path)
    assert Indice.cargar(tmp_path / "no-existe", emb, c) is None
    class Otro(EmbedderHash):
        nombre = "otro"
    assert Indice.cargar(tmp_path, Otro(), c) is None  # otro embedder: los vectores ya no sirven
    c.execute("INSERT INTO fragmentos (fuente_id, tipo, ref, titulo, texto) VALUES (1, 'catalogo', 'catalogo:TMP', 't', 'x')")
    assert Indice.cargar(tmp_path, emb, c) is None  # cambiaron los fragmentos
    c.execute("DELETE FROM fragmentos WHERE ref = 'catalogo:TMP'")
    c.commit()


def test_reindexar_reporta_conteos_y_tiempos(dataset):
    r = reindexar(dataset["conn"], dataset["embedder"])
    assert r["fragmentos"] >= 105 and r["embedder"] == "hash-ngramas" and r["segundos_vectores"] >= 0


# --------------------------------------------------------------------------- embedder y fichas
def test_embedder_hash_es_determinista_y_normalizado():
    e = EmbedderHash()
    a, b = e.codificar(["cable THW calibre 12"]), e.codificar(["cable THW calibre 12"])
    assert np.array_equal(a, b) and np.linalg.norm(a[0]) == pytest.approx(1.0)
    parecido = float((e.codificar(["cable THW calibre 12 negro"]) @ a.T)[0, 0])
    distinto = float((e.codificar(["gabinete metálico NEMA 4X"]) @ a.T)[0, 0])
    assert parecido > distinto


def test_crear_embedder_valida_el_nombre(monkeypatch):
    assert crear_embedder("hash").nombre == "hash-ngramas"
    with pytest.raises(ValueError, match="TESSERA_EMBEDDER"):
        crear_embedder("gpt")


def test_normalizar_texto():
    assert normalizar_texto("  Instalación   Eléctrica ") == "instalacion electrica"


def test_trozos_de_ficha_respetan_el_tamano():
    texto = "\n".join(f"Línea {i} " + "x" * 60 for i in range(40))
    partes = _trozos(texto, tam=300)
    assert len(partes) > 3 and all(len(p) <= 400 for p in partes) and _trozos("") == []
