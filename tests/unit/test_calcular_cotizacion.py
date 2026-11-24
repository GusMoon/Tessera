"""Calculadora determinista: paridad con la interfaz (fixture compartido), márgenes, premium y validaciones."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tools.calcular_cotizacion import (
    ESCENARIOS,
    Linea,
    calcular_cotizacion,
    div_redondeada,
    precio_con_margen,
    totales,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = RAIZ / "tests" / "fixtures" / "calculo_casos.json"
FIXTURE_WEB = RAIZ / "web" / "src" / "lib" / "calculo_casos.fixture.json"
CASOS = json.loads(FIXTURE.read_text(encoding="utf-8"))["casos"]


def test_el_fixture_de_la_interfaz_es_idéntico():
    assert FIXTURE.read_bytes() == FIXTURE_WEB.read_bytes()


@pytest.mark.parametrize("caso", CASOS, ids=[c["nombre"] for c in CASOS])
def test_paridad_con_calculo_ts(caso):
    importes = [l["cantidad"] * l["precioUnitario"] for l in caso["lineas"]]
    costos = [l["cantidad"] * l["costoUnitario"] for l in caso["lineas"]]
    r = totales(importes, costos, caso["tasaIvaPorciento"])
    e = caso["esperado"]
    assert importes == e["importes"]
    assert (r["subtotal_centavos"], r["iva_centavos"], r["total_centavos"]) == (e["subtotal"], e["iva"], e["total"])
    assert (r["costo_centavos"], r["margen_centavos"], r["margen_puntos_base"]) == (e["costo"], e["margen"], e["margenPuntosBase"])


def test_div_redondeada_medio_hacia_afuera():
    assert [div_redondeada(n, 2) for n in (1, 3, -1, -3, 0)] == [1, 2, -1, -2, 0]
    with pytest.raises(ValueError):
        div_redondeada(1, 0)


def test_precio_con_margen_sobre_el_precio_de_venta():
    # 18 % sobre el precio: 1 000.00 / 0.82 = 1 219.5122 → 1 219.51
    assert precio_con_margen(100_000, 1800) == 121_951
    assert precio_con_margen(100_000, 0) == 100_000
    with pytest.raises(ValueError):
        precio_con_margen(100, 10_000)


def linea(codigo="A", cantidad=2, costo=100_000, **kw):
    return Linea(tipo=kw.pop("tipo", "material"), codigo=codigo, concepto=f"Concepto {codigo}", unidad="PZA", cantidad=cantidad,
                 costo_unitario_centavos=costo, fuente_ref=f"catalogo:{codigo}", **kw)


def test_tres_escenarios_mismo_costo_distinto_margen():
    r = calcular_cotizacion([linea()])
    assert tuple(r) == ESCENARIOS
    precios = [r[e]["partidas"][0]["precio_unitario_centavos"] for e in ESCENARIOS]
    assert precios == [113_636, 121_951, 133_333]  # costo 1 000.00 con 12 %, 18 % y 25 %
    assert precios == sorted(precios)
    assert all(r[e]["costo_centavos"] == 200_000 for e in ESCENARIOS)
    # El margen real calculado sobre el subtotal queda cerca del objetivo (el redondeo a centavo lo mueve poco).
    assert abs(r["recomendado"]["margen_puntos_base"] - 1800) <= 2


def test_totales_coinciden_con_importes_mas_iva():
    r = calcular_cotizacion([linea("A", 3, 12_345), linea("B", 7, 999)])
    for e in r.values():
        suma = sum(p["importe_centavos"] for p in e["partidas"])
        assert e["subtotal_centavos"] == suma
        assert e["iva_centavos"] == div_redondeada(suma * 16, 100)
        assert e["total_centavos"] == suma + e["iva_centavos"]


def test_servicios_premium_solo_entran_al_premium():
    r = calcular_cotizacion([linea(), linea("SRV", 1, 180_000, tipo="servicio", incluir_en="premium")])
    assert [len(r[e]["partidas"]) for e in ESCENARIOS] == [1, 1, 2]
    assert [p["orden"] for p in r["premium"]["partidas"]] == [1, 2]


def test_marca_precios_de_mas_de_seis_meses():
    r = calcular_cotizacion([linea("A", antiguedad_meses=6), linea("B", antiguedad_meses=7)])
    marcas = {p["codigo"]: p["precio_antiguo"] for p in r["economico"]["partidas"]}
    assert marcas == {"A": False, "B": True}  # «más de 6 meses»: 7 o más meses cumplidos


def test_marca_partidas_duplicadas():
    r = calcular_cotizacion([linea("A"), linea("B"), linea("A", 5)])
    assert [p["duplicada"] for p in r["economico"]["partidas"]] == [True, False, True]


def test_toda_partida_conserva_su_fuente():
    r = calcular_cotizacion([linea("A", fuente_fecha="2026-10-01")])
    for e in r.values():
        assert e["partidas"][0]["fuente_ref"] == "catalogo:A" and e["partidas"][0]["fuente_fecha"] == "2026-10-01"


@pytest.mark.parametrize(
    "kwargs",
    [{"cantidad": 0}, {"cantidad": -1}, {"cantidad": 1.5}, {"cantidad": True}, {"costo": -1}, {"costo": 10.5}],
)
def test_rechaza_cantidades_y_costos_invalidos(kwargs):
    with pytest.raises(ValueError):
        linea(**kwargs)


def test_rechaza_partida_sin_fuente():
    with pytest.raises(ValueError, match="fuente"):
        Linea(tipo="material", codigo="X", concepto="x", unidad="PZA", cantidad=1, costo_unitario_centavos=1, fuente_ref="")


def test_rechaza_margenes_incompletos():
    with pytest.raises(ValueError, match="Faltan"):
        calcular_cotizacion([linea()], {"economico": 1000})


def test_sin_partidas_no_hay_margen():
    r = calcular_cotizacion([])
    assert r["premium"]["subtotal_centavos"] == 0 and r["premium"]["margen_puntos_base"] is None
