"""Orquestador: el LLM solo redacta; sus cifras se validan; ante fallos queda el resultado determinista. Memoria y bitácora."""

from __future__ import annotations

import json

import pytest

from agent import bitacora
from agent.llm import ErrorLimiteLLM, RespuestaLLM
from agent.memory import memoria
from agent.orquestador import cifras_no_respaldadas, construir_contexto, orquestar, pesos

SOLICITUD = "20 gabinetes NEMA 4X intemperie 40x30x20 con instalación y flete a Umán"


class Proveedor:
    """LLM falso: devuelve el texto indicado y guarda lo que recibió."""

    nombre = "falso"

    def __init__(self, texto=None, error=None):
        self.texto, self.error, self.recibido = texto, error, []

    def completar(self, mensajes, *, sistema=None, **kw):
        self.recibido.append((mensajes, sistema))
        if self.error:
            raise self.error
        return RespuestaLLM(texto=self.texto, modelo="modelo-falso", proveedor="falso", latencia_s=0.5)


def redaccion_valida(extra=""):
    return json.dumps({e: {"notas": f"Nota del escenario {e}. {extra}", "riesgos": ["Confirma vigencia de precios."]}
                       for e in ("economico", "recomendado", "premium")})


def correr(dataset, **kw):
    return orquestar(SOLICITUD, "u1", dataset["conn"], dataset["indice"], registrar_bitacora=False, **kw)


# --------------------------------------------------------------------------- validación de cifras
def test_cifras_no_respaldadas():
    contexto = "20 pza a $2,012.20 MXN, total $48,000.00 MXN, margen 18 %"
    assert cifras_no_respaldadas("Son 20 piezas a $2,012.20", contexto) == set()
    assert cifras_no_respaldadas("Total de $50,000.00 y 20 piezas", contexto) == {"50000"}
    assert cifras_no_respaldadas("sin cifras", contexto) == set()
    assert cifras_no_respaldadas("48000", contexto) == set()  # misma cifra sin comas ni ceros finales


def test_pesos():
    assert pesos(123456) == "$1,234.56 MXN"


# --------------------------------------------------------------------------- redacción
def test_sin_proveedor_ni_demo_el_resultado_es_determinista(dataset):
    r = correr(dataset, proveedor=None, modo_demo=False)
    assert r["estado"] == "completa" and r["redaccion"]["origen"] == "determinista"
    assert all(r["redaccion"]["escenarios"][e]["notas"] == "" for e in ("economico", "recomendado", "premium"))


def test_el_llm_redacta_y_no_toca_los_numeros(dataset):
    sin_llm = correr(dataset, proveedor=None, modo_demo=False)
    prov = Proveedor(redaccion_valida())
    r = correr(dataset, proveedor=prov, modo_demo=False)
    assert r["redaccion"]["origen"] == "llm" and r["redaccion"]["modelo"] == "modelo-falso"
    assert r["redaccion"]["escenarios"]["premium"]["notas"].startswith("Nota del escenario premium")
    assert r["escenarios"] == sin_llm["escenarios"]  # los totales salen igual con o sin modelo (regla 1)
    mensajes, sistema = prov.recibido[0]
    assert "$" in mensajes[0]["content"] and "Reglas" in sistema


def test_se_descarta_el_texto_con_cifras_inventadas(dataset):
    r = correr(dataset, proveedor=Proveedor(redaccion_valida("Ahorras $99,999.99 MXN.")), modo_demo=False)
    assert r["redaccion"]["origen"] == "determinista" and "99999.99" in r["redaccion"]["aviso"]
    assert all(r["redaccion"]["escenarios"][e]["notas"] == "" for e in ("economico", "recomendado", "premium"))


def test_se_acepta_una_cifra_que_si_viene_de_las_herramientas(dataset):
    total = correr(dataset, proveedor=None, modo_demo=False)["escenarios"]["recomendado"]["total_centavos"]
    r = correr(dataset, proveedor=Proveedor(redaccion_valida(f"El total es {pesos(total)}.")), modo_demo=False)
    assert r["redaccion"]["origen"] == "llm"


@pytest.mark.parametrize("prov", [Proveedor(error=ErrorLimiteLLM("429", 30)), Proveedor("esto no es JSON")])
def test_si_el_modelo_falla_queda_el_resultado_sin_redaccion(dataset, prov):
    r = correr(dataset, proveedor=prov, modo_demo=False)
    assert r["estado"] == "completa" and r["escenarios"] and r["redaccion"]["origen"] == "determinista" and r["redaccion"]["aviso"]


def test_modo_demo_usa_las_respuestas_precargadas_y_no_llama_al_modelo(dataset):
    prov = Proveedor(redaccion_valida())
    r = correr(dataset, proveedor=prov, modo_demo=True)
    assert r["redaccion"]["origen"] == "demo" and prov.recibido == []
    assert r["redaccion"]["escenarios"]["premium"]["notas"]
    assert all(c not in "".join(e["notas"] for e in r["redaccion"]["escenarios"].values()) for c in "0123456789")  # sin cifras


def test_si_falta_aclarar_no_se_calcula_ni_se_llama_al_modelo(dataset):
    prov = Proveedor(redaccion_valida())
    r = orquestar("10 cables calibre 12", "u1", dataset["conn"], dataset["indice"], proveedor=prov, modo_demo=False, registrar_bitacora=False)
    assert r["estado"] == "requiere_aclaracion" and r["escenarios"] is None and r["preguntas"] and prov.recibido == []


def test_el_contexto_trae_fuentes_y_memoria_confirmada(dataset):
    r = correr(dataset, proveedor=None, modo_demo=False)
    ctx = construir_contexto(r, [{"texto": "Cliente X paga a 30 días", "origen": "Marcos"}])
    assert "catalogo:GAB-403020" in ctx and "Cliente X paga a 30 días" in ctx and "Escenario premium" in ctx


# --------------------------------------------------------------------------- memoria
def test_memoria_solo_inyecta_hechos_activos_y_confirmados(dataset):
    c = dataset["conn"]
    c.execute("DELETE FROM memoria")
    a = memoria.agregar(c, "Altabrisa pide factura con RFC", "cotización COT-MID-0101")
    b = memoria.agregar(c, "Montebello paga a 60 días", "Marcos", confirmado=True)
    p = memoria.agregar(c, "Dato pausado", "Ana", confirmado=True)
    memoria.cambiar_estado(c, p, "Pausada")
    assert [h["id"] for h in memoria.para_contexto(c)] == [b]  # a está «por confirmar»; p está pausado
    memoria.confirmar(c, a)
    assert {h["id"] for h in memoria.para_contexto(c)} == {a, b}
    memoria.editar(c, a, "Altabrisa pide factura con RFC y orden de compra")
    assert a not in {h["id"] for h in memoria.para_contexto(c)}  # lo editado vuelve a pedir confirmación
    memoria.borrar(c, a)
    assert a not in {h["id"] for h in memoria.listar(c)}
    c.execute("DELETE FROM memoria")


def test_memoria_valida_y_exige_origen(dataset):
    c = dataset["conn"]
    with pytest.raises(ValueError):
        memoria.agregar(c, "  ", "x")
    with pytest.raises(ValueError):
        memoria.agregar(c, "algo", " ")
    with pytest.raises(ValueError):
        memoria.cambiar_estado(c, 1, "Borrada")
    with pytest.raises(KeyError):
        memoria.confirmar(c, 9999)


def test_los_hechos_confirmados_llegan_al_modelo(dataset):
    c = dataset["conn"]
    c.execute("DELETE FROM memoria")
    memoria.agregar(c, "Preferir entregas en la mañana", "Ana", confirmado=True)
    memoria.agregar(c, "Dato sin confirmar", "Ana")
    prov = Proveedor(redaccion_valida())
    correr(dataset, proveedor=prov, modo_demo=False)
    enviado = prov.recibido[0][0][0]["content"]
    assert "Preferir entregas en la mañana" in enviado and "Dato sin confirmar" not in enviado
    c.execute("DELETE FROM memoria")


# --------------------------------------------------------------------------- bitácora
def test_la_bitacora_registra_fuentes_y_herramientas(dataset):
    c = dataset["conn"]
    c.execute("DELETE FROM bitacora")
    orquestar(SOLICITUD, "u1", c, dataset["indice"], proveedor=None, modo_demo=True)
    fila = bitacora.listar(c)[0]
    assert fila["usuario"] == "u1" and fila["pregunta"] == SOLICITUD
    assert "catalogo:GAB-403020" in fila["documentos"] and "calcular_cotizacion" in fila["herramientas"] and "redaccion:demo" in fila["herramientas"]
    assert fila["duracion_ms"] >= 0
    c.execute("DELETE FROM bitacora")
