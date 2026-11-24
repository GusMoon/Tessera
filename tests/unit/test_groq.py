"""Pruebas del proveedor Groq y de su medidor de límites. Sin red ni claves reales."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from agent.llm import ConfigLLM, ErrorAutenticacionLLM, ErrorConfiguracionLLM, ErrorLimiteLLM, ErrorLLM, UsoAcumulado, crear_proveedor
from agent.llm import proveedores
from agent.llm.limites import LimitesGroq, parsear_duracion
from api import chat as modulo_chat
from api.main import app

CLAVE_FALSA = "gsk_clave-de-prueba-no-real-abcd1234"
cliente_api = TestClient(app)

CABECERAS = {
    "x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "990", "x-ratelimit-reset-requests": "2m59.5s",
    "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7500", "x-ratelimit-reset-tokens": "7.5s",
}


def cfg(**kw) -> ConfigLLM:
    return ConfigLLM(_env_file=None, **kw)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for v in ("LLM_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "GROQ_REASONING_EFFORT", "OPENROUTER_API_KEY", "OPENROUTER_MODELS",
              "OPENROUTER_MODEL_VISION", "LLM_MAX_TOKENS_SALIDA"):
        monkeypatch.delenv(v, raising=False)


# --------------------------------------------------------------------------- duraciones y límites
@pytest.mark.parametrize("texto,esperado", [("2m59.56s", 179.56), ("7.66s", 7.66), ("250ms", 0.25), ("1h2m3s", 3723.0), ("", None), ("pronto", None), ("5", None)])
def test_parsear_duracion(texto, esperado):
    resultado = parsear_duracion(texto)
    assert resultado == pytest.approx(esperado) if esperado is not None else resultado is None


def test_limites_sin_datos_devuelve_none():
    assert LimitesGroq().instantanea() is None


def test_limites_ignora_respuestas_sin_cabeceras_de_limite():
    lim = LimitesGroq()
    lim.actualizar(CABECERAS, ahora=100.0)
    lim.actualizar({"content-type": "application/json"}, ahora=105.0)  # p. ej. una respuesta de error ajena
    assert lim.instantanea(ahora=100.0)["restantes_tokens_minuto"] == 7500


def test_limites_lee_las_cabeceras_y_descuenta_el_tiempo_transcurrido():
    lim = LimitesGroq()
    lim.actualizar({k.upper(): v for k, v in CABECERAS.items()}, ahora=100.0)  # no distingue mayúsculas
    d = lim.instantanea(ahora=104.0)
    assert (d["limite_peticiones_dia"], d["restantes_peticiones_dia"]) == (1000, 990)
    assert (d["limite_tokens_minuto"], d["restantes_tokens_minuto"]) == (8000, 7500)
    assert d["reinicio_tokens_s"] == pytest.approx(3.5) and d["reinicio_peticiones_s"] == pytest.approx(175.5)


def test_limites_ventana_de_tokens_vencida_vuelve_al_tope():
    lim = LimitesGroq()
    lim.actualizar(CABECERAS, ahora=100.0)
    d = lim.instantanea(ahora=200.0)  # pasaron 100 s: la ventana de 7.5 s ya se reinició
    assert d["reinicio_tokens_s"] == 0.0 and d["restantes_tokens_minuto"] == 8000


def test_el_gancho_de_httpx_captura_las_cabeceras_de_una_respuesta_real():
    lim = LimitesGroq()
    transporte = httpx.MockTransport(lambda req: httpx.Response(200, json={}, headers=CABECERAS))
    with httpx.Client(transport=transporte, event_hooks={"response": [lim.registrar_respuesta]}) as c:
        c.get("https://x.invalid/chat")
    assert lim.instantanea()["restantes_peticiones_dia"] == 990


# --------------------------------------------------------------------------- fábrica
@pytest.fixture
def openai_falso(monkeypatch):
    clase = MagicMock(name="OpenAI")
    monkeypatch.setattr(proveedores, "OpenAI", clase)
    return clase


def test_groq_se_crea_con_url_modelo_y_esfuerzo_de_razonamiento(openai_falso):
    p = crear_proveedor(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))
    kw = openai_falso.call_args.kwargs
    assert p.nombre == "groq" and p.modelos == ["openai/gpt-oss-20b"]
    assert kw["base_url"] == "https://api.groq.com/openai/v1" and kw["api_key"] == CLAVE_FALSA
    assert p._extra_body == {"reasoning_effort": "low"}
    assert isinstance(p.limites, LimitesGroq)
    # El cliente HTTP lleva el gancho que alimenta el medidor.
    assert kw["http_client"].event_hooks["response"] == [p.limites.registrar_respuesta]


def test_groq_esfuerzo_vacio_no_se_envia_y_el_modelo_se_puede_cambiar(openai_falso):
    p = crear_proveedor(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA, groq_model="openai/gpt-oss-120b", groq_reasoning_effort=""))
    assert p.modelos == ["openai/gpt-oss-120b"] and p._extra_body is None


def test_groq_sin_clave_falla_con_mensaje_claro():
    with pytest.raises(ErrorConfiguracionLLM, match="GROQ_API_KEY"):
        crear_proveedor(cfg(llm_provider="groq"))


def test_groq_con_modelo_vacio_falla():
    with pytest.raises(ErrorConfiguracionLLM, match="GROQ_MODEL"):
        crear_proveedor(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA, groq_model=" "))


def test_la_clave_de_groq_no_aparece_en_repr_ni_en_el_enmascarado(openai_falso):
    p = crear_proveedor(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))
    assert CLAVE_FALSA not in repr(p) and CLAVE_FALSA not in repr(cfg(groq_api_key=CLAVE_FALSA))


# --------------------------------------------------------------------------- errores traducidos
def error_openai(clase, estado, mensaje, cabeceras=None):
    req = httpx.Request("POST", "https://ejemplo.invalid/chat/completions")
    return clase(mensaje, response=httpx.Response(estado, request=req, headers=cabeceras or {}), body=None)


@pytest.fixture
def groq(openai_falso):
    return crear_proveedor(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))


def test_groq_401_no_revela_la_clave(groq):
    err = groq._traducir(error_openai(openai.AuthenticationError, 401, f"bad key {CLAVE_FALSA}"))
    assert isinstance(err, ErrorAutenticacionLLM) and "GROQ_API_KEY" in str(err) and CLAVE_FALSA not in str(err)


def test_groq_429_explica_los_limites_y_trae_la_espera(groq):
    err = groq._traducir(error_openai(openai.RateLimitError, 429, "limit", {"retry-after": "12"}))
    assert isinstance(err, ErrorLimiteLLM) and err.reintentar_en_s == 12
    assert "tokens" in str(err) and "12 s" in str(err) and "OpenRouter" not in str(err)


def test_groq_413_pide_un_archivo_mas_corto(groq):
    err = groq._traducir(error_openai(openai.APIStatusError, 413, "Request too large"))
    assert isinstance(err, ErrorLLM) and "413" in str(err) and "más corto" in str(err)


def test_groq_modelo_invalido_apunta_al_env(groq):
    err = groq._traducir(error_openai(openai.NotFoundError, 404, "no model"))
    assert "GROQ_MODEL" in str(err)


# --------------------------------------------------------------------------- API
def test_imagen_con_groq_se_envia_por_openrouter():
    c = cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA, openrouter_api_key="sk-or-v1-falsa")
    v = modulo_chat._config_vision(c)
    assert v.llm_provider == "openrouter" and v.modelos_openrouter == ["nvidia/nemotron-3.5-super-vl:free"]


def test_imagen_con_groq_sin_clave_de_openrouter_da_un_error_claro():
    with pytest.raises(ErrorConfiguracionLLM, match="OPENROUTER_API_KEY"):
        modulo_chat._config_vision(cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))


def test_tope_de_salida_es_menor_con_groq():
    assert modulo_chat._max_tokens_salida("groq") == 1024
    assert modulo_chat._max_tokens_salida("openrouter") == 2048


@pytest.fixture
def api_groq(monkeypatch):
    monkeypatch.setattr(modulo_chat, "ConfigLLM", lambda: cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))
    monkeypatch.setattr(modulo_chat, "_proveedores", {})


def test_uso_groq_antes_del_primer_mensaje_no_gasta_peticiones(api_groq):
    cuerpo = cliente_api.get("/api/chat/uso").json()
    assert cuerpo["proveedor"] == "groq" and cuerpo["tipo_limite"] == "peticiones y tokens"
    assert cuerpo["dia"] is None and cuerpo["tokens_minuto"] is None and "envía un mensaje" in cuerpo["aviso"]


def test_uso_groq_con_datos_de_las_cabeceras(api_groq):
    lim = LimitesGroq()
    lim.actualizar(CABECERAS, ahora=__import__("time").time())
    modulo_chat._proveedores["texto"] = SimpleNamespace(limites=lim, uso=UsoAcumulado(llamadas=2, tokens_entrada=900, tokens_salida=300))
    r = cliente_api.get("/api/chat/uso")
    cuerpo = r.json()
    assert cuerpo["dia"] == {"usadas": 10, "limite": 1000, "restantes": 990}
    assert cuerpo["tokens_minuto"]["restantes"] == 7500 and cuerpo["tokens_minuto"]["limite"] == 8000
    assert 0 < cuerpo["tokens_minuto"]["segundos_para_reiniciar"] <= 7.5
    assert cuerpo["reinicio_dia_utc"].endswith("Z") and cuerpo["sesion"]["tokens_total"] == 1200
    assert cuerpo["reinicio_modo"] == "recarga"  # Groq recarga de forma continua: no es un corte diario
    assert CLAVE_FALSA not in r.text


def test_config_con_groq_ofrece_vision_solo_si_hay_clave_de_openrouter(monkeypatch):
    monkeypatch.setattr(modulo_chat, "ConfigLLM", lambda: cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA))
    assert cliente_api.get("/api/chat/config").json() == {"proveedor": "groq", "modelo": "openai/gpt-oss-20b", "modelo_vision": None}
    monkeypatch.setattr(modulo_chat, "ConfigLLM", lambda: cfg(llm_provider="groq", groq_api_key=CLAVE_FALSA, openrouter_api_key="sk-or-v1-falsa"))
    assert cliente_api.get("/api/chat/config").json()["modelo_vision"] == "nvidia/nemotron-3.5-super-vl:free"
