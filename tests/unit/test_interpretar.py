"""Intérprete determinista: cantidades, unidades, ambigüedad, servicios y preguntas en lugar de inventar."""

from __future__ import annotations

import pytest

from agent.interpretar import (
    _leer_cantidad,
    _numeros_compuestos,
    cobertura,
    interpretar,
    tokens_comparacion,
)


def interp(dataset, texto, usuario="u1", **kw):
    return interpretar(texto, dataset["conn"], dataset["indice"], usuario, **kw)


def materiales(r):
    return sorted((l.codigo, l.cantidad) for l in r.lineas if l.tipo == "material")


def servicios(r):
    return sorted((l.codigo, l.cantidad) for l in r.lineas if l.tipo == "servicio")


# --------------------------------------------------------------------------- utilidades de texto
def test_tokens_separan_numeros_de_letras_y_unifican_plurales():
    assert tokens_comparacion("Interruptores 1P 20A") == ["interruptor", "1", "20"]
    assert tokens_comparacion("tubos conduit de 3/4 pulgadas") == ["tubo", "conduit", "de", "3/4", "pulg"]
    assert cobertura(["a", "b"], ["a"]) == 0.5 and cobertura([], ["a"]) == 0.0


@pytest.mark.parametrize(
    "texto,esperado",
    [("treinta y cinco tubos", "35 tubos"), ("una docena de cajas", "12 de cajas"), ("media docena de cajas", "6 de cajas"),
     ("dos docenas de cajas", "24 de cajas")],
)
def test_numeros_compuestos(texto, esperado):
    assert _numeros_compuestos(texto) == esperado


@pytest.mark.parametrize(
    "texto,cantidad,resto,unidad",
    [("20 gabinetes nema 4x", 20, "gabinetes nema 4x", None), ("veinte rollos de cable", 20, "cable", "rollos"),
     ("un gabinete", 1, "gabinete", None), ("3 piezas de cople", 3, "cople", "piezas"), ("tubo conduit", None, "tubo conduit", None)],
)
def test_leer_cantidad(texto, cantidad, resto, unidad):
    c, r, u, problema = _leer_cantidad(texto)
    assert (c, r, u, problema) == (cantidad, resto, unidad, None)


def test_cantidad_con_decimales_se_rechaza():
    assert _leer_cantidad("2.5 rollos de cable")[3] is not None


# --------------------------------------------------------------------------- materiales
def test_resuelve_cantidades_y_articulos(dataset):
    r = interp(dataset, "Necesito 20 gabinetes NEMA 4X intemperie 40x30x20 y 100 rollos de cable THW calibre 12 negro")
    assert r.completa and materiales(r) == [("CAB-THW-12N", 100), ("GAB-403020", 20)]
    assert all(l.fuente_ref.startswith("catalogo:") for l in r.lineas if l.tipo == "material")


def test_acepta_numeros_en_palabras_y_relleno(dataset):
    r = interp(dataset, "Hola, por favor cotízame veinte interruptores termomagnéticos 1P 20A y dos centros de carga 4 polos bifásico")
    assert materiales(r) == [("CC-4P-BIF", 2), ("INT-TM-120", 20)]


def test_una_docena(dataset):
    r = interp(dataset, "una docena de interruptores termomagnéticos 1P 20A")
    assert materiales(r) == [("INT-TM-120", 12)]


def test_hereda_el_sustantivo_del_renglon_anterior(dataset):
    r = interp(dataset, "5 tubos PVC hidráulico 3/4, 15 de 1 pulg y 50 de 2 pulg")
    assert materiales(r) == [("TUB-PVC-H075", 5), ("TUB-PVC-H100", 15), ("TUB-PVC-H200", 50)]


def test_el_mismo_articulo_dos_veces_se_suma_y_se_avisa(dataset):
    r = interp(dataset, "10 gabinetes NEMA 4X, 5 gabinetes NEMA 4X")
    assert materiales(r) == [("GAB-403020", 15)] and any("más de una vez" in a for a in r.avisos)


# --------------------------------------------------------------------------- preguntas (no inventar)
def test_pregunta_si_hay_dos_articulos_posibles(dataset):
    r = interp(dataset, "10 cables calibre 12")
    assert not r.completa and any("CAB-THW-12N" in q and "CAB-THW-12R" in q for q in r.preguntas)
    assert materiales(r) == []


def test_pregunta_si_la_unidad_no_coincide_con_la_del_catalogo(dataset):
    r = interp(dataset, "50 metros de cable THW calibre 12 negro")
    assert not r.completa and any("rollo" in q for q in r.preguntas)


def test_pregunta_la_cantidad_si_falta(dataset):
    r = interp(dataset, "gabinete NEMA 4X intemperie 40x30x20")
    assert any(q.startswith("¿Cuántas unidades") for q in r.preguntas) and materiales(r) == []


def test_pregunta_si_no_encuentra_el_material(dataset):
    r = interp(dataset, "20 turbinas de helicóptero")
    assert not r.completa and any("No encontré" in q for q in r.preguntas)


def test_pregunta_si_no_hay_materiales(dataset):
    r = interp(dataset, "buenos días, ¿me ayudas?")
    assert not r.completa and r.preguntas and not r.lineas


def test_pregunta_la_zona_si_pide_flete_sin_zona(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X con flete")
    assert any("zona" in q for q in r.preguntas)


# --------------------------------------------------------------------------- servicios
def test_instalacion_usa_la_tarifa_de_cada_categoria(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X y 2 centros de carga 4 polos bifásico, con instalación")
    assert ("SRV-INS-GAB", 20) in servicios(r) and ("SRV-INS-TAB", 2) in servicios(r)


def test_instalacion_con_alcance_solo_toma_esa_categoria(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X y 2 centros de carga 4 polos bifásico. Instalación de los gabinetes")
    assert [c for c, _ in servicios(r) if c.startswith("SRV-INS")] == ["SRV-INS-GAB"]


def test_instalacion_incluida(dataset):
    r = interp(dataset, "12 interruptores termomagnéticos 1P 20A. Instalación incluida.")
    assert ("SRV-INS-INT", 12) in servicios(r)


def test_instalacion_de_canalizacion_se_calcula_en_metros(dataset):
    r = interp(dataset, "10 tramos de tubo conduit pared delgada 3/4 y 20 coples conduit pared delgada 3/4, con instalación")
    assert ("SRV-INS-CON", 30) in servicios(r)  # solo el tubo: 10 tramos × 3 m; los coples no son metros


def test_flete_por_zona_y_por_viajes(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X. Flete a Umán")
    assert ("SRV-FLE-UMA", 1) in servicios(r)
    r = interp(dataset, "20 gabinetes NEMA 4X. Flete a Progreso, 2 viajes")
    assert ("SRV-FLE-PRO", 2) in servicios(r)


def test_zona_mencionada_incluye_flete_y_avisa(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X para la obra en Motul")
    assert ("SRV-FLE-MOT", 1) in servicios(r) and any("Motul" in a for a in r.avisos)


def test_el_nombre_del_cliente_no_se_toma_como_destino(dataset):
    r = interp(dataset, "Cotización para Grupo Constructor Kanasín: 20 gabinetes NEMA 4X")
    assert r.cliente == "Grupo Constructor Kanasín" and servicios(r) == [("SRV-OPC-GAR", 1), ("SRV-OPC-SUP", 1)]


def test_los_opcionales_premium_se_agregan_siempre_con_su_marca(dataset):
    r = interp(dataset, "20 gabinetes NEMA 4X")
    opcionales = [l for l in r.lineas if l.incluir_en == "premium"]
    assert sorted(l.codigo for l in opcionales) == ["SRV-OPC-GAR", "SRV-OPC-SUP"]
    assert not [l for l in interp(dataset, "20 gabinetes NEMA 4X", incluir_opcionales=False).lineas if l.tipo == "servicio"]


def test_los_precios_viejos_llegan_marcados(dataset):
    r = interp(dataset, "20 interruptores termomagnéticos 1P 20A")  # catálogo de 8 meses
    linea = next(l for l in r.lineas if l.codigo == "INT-TM-120")
    assert linea.antiguedad_meses > 6 and linea.fuente_fecha


def test_precio_del_catalogo_en_centavos_exactos(dataset):
    r = interp(dataset, "30 coples conduit pared delgada 3/4 pulg con tornillo")
    assert next(l for l in r.lineas if l.codigo == "COP-CND-075").costo_unitario_centavos == 1250  # $12.50
