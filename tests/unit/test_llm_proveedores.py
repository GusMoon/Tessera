"""Pruebas de la configuración de proveedores de LLM. Todo con mocks: sin red ni claves reales."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai
import pytest

from agent.llm import (
    ConfigLLM,
    ErrorAutenticacionLLM,
    ErrorConfiguracionLLM,
    ErrorLimiteLLM,
    ErrorModeloNoDisponibleLLM,
    ErrorRedLLM,
    crear_proveedor,
    enmascarar,
    redactar,
)
from agent.llm import proveedores

# Clave FALSA, solo para probar el enmascarado. No es una credencial real.
CLAVE_FALSA = "sk-or-v1-clave-de-prueba-no-real-abcd1234"
VARIABLES = [
    "LLM_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODELS", "OPENROUTER_REFERER",
    "OPENROUTER_TITLE", "OLLAMA_BASE_URL", "OLLAMA_MODEL", "MODO_DEMO",
    "LLM_MAX_TOKENS_SALIDA", "LLM_TEMPERATURA", "LLM_CONTEXTO_ENTRADA",
]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Aísla las pruebas del entorno y del .env real de quien las ejecuta."""
    for v in VARIABLES:
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def openai_falso(monkeypatch):
    """Sustituye el cliente OpenAI por un mock; devuelve (clase_mock, cliente_mock)."""
    clase = MagicMock(name="OpenAI")
    monkeypatch.setattr(proveedores, "OpenAI", clase)
    return clase, clase.return_value


def cfg(**kw) -> ConfigLLM:
    return ConfigLLM(_env_file=None, **kw)


def respuesta_falsa(modelo="modelo-x:free", texto="OK"):
    return SimpleNamespace(model=modelo, choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


def error_openai(clase, estado, mensaje):
    req = httpx.Request("POST", "https://ejemplo.invalid/chat/completions")
    return clase(mensaje, response=httpx.Response(estado, request=req), body=None)


# ------------------------------------------------------------------ selección de proveedor
def test_proveedor_predeterminado_es_ollama(openai_falso):
    clase, _ = openai_falso
    p = crear_proveedor(cfg())
    assert p.nombre == "ollama"
    assert p.modelos == ["qwen2.5:3b-instruct"]
    kw = clase.call_args.kwargs
    assert kw["base_url"] == "http://localhost:11434/v1"
    assert kw["api_key"] == "ollama"  # marcador, no una clave


def test_ollama_usa_url_y_modelo_configurados(openai_falso):
    clase, _ = openai_falso
    p = crear_proveedor(cfg(llm_provider="ollama", ollama_base_url="http://otro:1234/v1", ollama_model="m:1b"))
    assert p.modelos == ["m:1b"]
    assert clase.call_args.kwargs["base_url"] == "http://otro:1234/v1"


def test_openrouter_se_selecciona_con_llm_provider(openai_falso):
    clase, _ = openai_falso
    p = crear_proveedor(cfg(
        llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA,
        openrouter_models="a/uno:free, b/dos:free", openrouter_referer="http://localhost", openrouter_title="Tessera",
    ))
    assert p.nombre == "openrouter"
    assert p.modelos == ["a/uno:free", "b/dos:free"]
    kw = clase.call_args.kwargs
    assert kw["base_url"] == "https://openrouter.ai/api/v1"
    assert kw["api_key"] == CLAVE_FALSA
    assert kw["default_headers"] == {"X-Title": "Tessera", "HTTP-Referer": "http://localhost"}


def test_seleccion_desde_variables_de_entorno(monkeypatch, openai_falso):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", CLAVE_FALSA)
    monkeypatch.setenv("OPENROUTER_MODELS", "a/uno:free")
    assert crear_proveedor(ConfigLLM(_env_file=None)).nombre == "openrouter"


def test_variable_vacia_usa_el_valor_por_defecto(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("OLLAMA_MODEL", "")
    c = ConfigLLM(_env_file=None)
    assert c.llm_provider == "ollama" and c.ollama_model == "qwen2.5:3b-instruct"


def test_proveedor_desconocido_falla_con_mensaje_claro():
    with pytest.raises(ErrorConfiguracionLLM, match="LLM_PROVIDER"):
        crear_proveedor(cfg(llm_provider="gpt-nube"))


def test_modo_demo_solo_se_lee(monkeypatch):
    assert cfg().modo_demo is False
    monkeypatch.setenv("MODO_DEMO", "true")
    assert ConfigLLM(_env_file=None).modo_demo is True


def test_openrouter_vacio_no_afecta_a_ollama(openai_falso):
    assert crear_proveedor(cfg(llm_provider="ollama", openrouter_models="")).nombre == "ollama"


# ------------------------------------------------------------------ failover y cabeceras
def test_openrouter_envia_models_para_failover(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.return_value = respuesta_falsa(modelo="b/dos:free")
    p = crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA,
                            openrouter_models="a/uno:free,b/dos:free"))
    r = p.completar([{"role": "user", "content": "hola"}])
    kw = cliente.chat.completions.create.call_args.kwargs
    assert kw["extra_body"] == {"models": ["a/uno:free", "b/dos:free"]}
    assert kw["model"] == "a/uno:free"
    assert r.modelo == "b/dos:free"  # el modelo que realmente respondió (failover)
    assert r.texto == "OK" and r.proveedor == "openrouter" and r.latencia_s >= 0


def test_ollama_no_envia_models(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.return_value = respuesta_falsa(modelo="qwen2.5:3b-instruct")
    crear_proveedor(cfg()).completar([{"role": "user", "content": "hola"}])
    assert "extra_body" not in cliente.chat.completions.create.call_args.kwargs


def test_cabeceras_opcionales_se_omiten_si_estan_vacias(openai_falso):
    clase, _ = openai_falso
    crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA,
                        openrouter_models="a/uno:free", openrouter_title=""))
    assert clase.call_args.kwargs["default_headers"] == {}


# ------------------------------------------------------------------ validación de :free, lista vacía, clave ausente
def test_modelo_sin_sufijo_free_falla(openai_falso):
    with pytest.raises(ErrorConfiguracionLLM, match=r":free") as e:
        crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA,
                            openrouter_models="a/uno:free,b/pago"))
    assert "b/pago" in str(e.value) and "cobros" in str(e.value)
    assert "a/uno:free" not in str(e.value)  # solo se señalan los que incumplen


def test_lista_de_modelos_vacia_falla(openai_falso):
    for valor in ("", " , ,"):
        with pytest.raises(ErrorConfiguracionLLM, match="OPENROUTER_MODELS está vacío"):
            crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models=valor))


def test_clave_ausente_falla(openai_falso):
    for clave in ("", "   "):
        with pytest.raises(ErrorConfiguracionLLM, match="OPENROUTER_API_KEY"):
            crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=clave, openrouter_models="a/uno:free"))


# ------------------------------------------------------------------ enmascarado de la clave
def test_enmascarar():
    assert enmascarar(CLAVE_FALSA) == "sk-or-v1-…1234"
    assert CLAVE_FALSA not in enmascarar(CLAVE_FALSA)
    assert enmascarar("") == "(vacía)" and enmascarar(None) == "(vacía)"
    assert enmascarar("corta") == "***"
    assert enmascarar("otra-clave-larga-9999") == "…9999"


def test_redactar_reemplaza_la_clave_en_cualquier_texto():
    texto = f"Incorrect API key provided: {CLAVE_FALSA}."
    assert CLAVE_FALSA not in redactar(texto, CLAVE_FALSA)
    assert "…1234" in redactar(texto, CLAVE_FALSA)


def test_repr_no_expone_la_clave(openai_falso):
    p = crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/uno:free"))
    c = cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA)
    for texto in (repr(p), str(p), repr(c), str(c)):
        assert CLAVE_FALSA not in texto


def test_errores_no_contienen_la_clave(openai_falso):
    _, cliente = openai_falso
    p = crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/uno:free"))
    casos = [
        error_openai(openai.AuthenticationError, 401, f"Incorrect API key provided: {CLAVE_FALSA}"),
        error_openai(openai.RateLimitError, 429, f"Rate limit for {CLAVE_FALSA}"),
        error_openai(openai.NotFoundError, 404, f"No endpoints found ({CLAVE_FALSA})"),
        error_openai(openai.InternalServerError, 500, f"fallo {CLAVE_FALSA}"),
        openai.APIConnectionError(request=httpx.Request("POST", "https://ejemplo.invalid")),
    ]
    for exc in casos:
        cliente.chat.completions.create.side_effect = exc
        with pytest.raises(Exception) as e:
            p.completar([{"role": "user", "content": "hola"}])
        assert CLAVE_FALSA not in str(e.value)
        assert e.value.__cause__ is None  # no se encadena el error original, que podría traer la clave


# ------------------------------------------------------------------ errores legibles
@pytest.mark.parametrize("exc, esperado, texto", [
    (error_openai(openai.AuthenticationError, 401, "x"), ErrorAutenticacionLLM, "401"),
    (error_openai(openai.RateLimitError, 429, "x"), ErrorLimiteLLM, "429"),
    (error_openai(openai.NotFoundError, 404, "x"), ErrorModeloNoDisponibleLLM, "OPENROUTER_MODELS"),
    (openai.APIConnectionError(request=httpx.Request("POST", "https://ejemplo.invalid")), ErrorRedLLM, "conexión"),
])
def test_errores_de_openrouter_son_legibles(openai_falso, exc, esperado, texto):
    _, cliente = openai_falso
    cliente.chat.completions.create.side_effect = exc
    p = crear_proveedor(cfg(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/uno:free"))
    with pytest.raises(esperado, match=texto):
        p.completar([{"role": "user", "content": "hola"}])


def test_ollama_modelo_ausente_sugiere_pull(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.side_effect = error_openai(openai.NotFoundError, 404, "model not found")
    with pytest.raises(ErrorModeloNoDisponibleLLM, match="ollama pull"):
        crear_proveedor(cfg()).completar([{"role": "user", "content": "hola"}])


def test_ollama_sin_servidor_sugiere_ollama_serve(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.side_effect = openai.APIConnectionError(
        request=httpx.Request("POST", "http://localhost:11434/v1"))
    with pytest.raises(ErrorRedLLM, match="ollama serve"):
        crear_proveedor(cfg()).completar([{"role": "user", "content": "hola"}])


# ------------------------------------------------------------------ gestión de tokens
from agent.llm import PROMPT_SISTEMA_COTIZACIONES, estimar_tokens, recortar_historial  # noqa: E402


def _msg(rol, n):
    # contenido único por mensaje para poder compararlos sin confundir turnos iguales
    _msg.contador = getattr(_msg, "contador", 0) + 1
    return {"role": rol, "content": f"{_msg.contador}:" + "x" * n}


def test_recortar_conserva_system_y_lo_mas_reciente():
    historial = [_msg("system", 30), _msg("user", 300), _msg("assistant", 300), _msg("user", 300),
                 _msg("assistant", 300), _msg("user", 30)]
    r = recortar_historial(historial, presupuesto=260)
    assert r[0]["role"] == "system" and r[-1] is historial[-1]
    assert len(r) < len(historial)
    assert r == [m for m in historial if any(m is x for x in r)]  # mismo orden cronológico
    assert historial[1] not in r  # lo más antiguo se descarta primero


def test_recortar_nunca_descarta_la_pregunta_actual():
    historial = [_msg("user", 100), _msg("user", 10_000)]
    assert recortar_historial(historial, presupuesto=50) == [historial[-1]]


def test_recortar_sin_presupuesto_no_cambia_nada():
    historial = [_msg("user", 10_000)] * 3
    assert recortar_historial(historial, 0) == historial


def test_estimar_tokens():
    assert estimar_tokens("") == 0
    assert estimar_tokens("a" * 300) > estimar_tokens("a" * 30) > 0


def test_completar_aplica_limites_por_defecto_y_registra_uso(openai_falso):
    _, cliente = openai_falso
    r = respuesta_falsa()
    r.usage = SimpleNamespace(prompt_tokens=120, completion_tokens=7)
    cliente.chat.completions.create.return_value = r
    p = crear_proveedor(cfg())
    resp = p.completar([{"role": "user", "content": "hola"}])
    kw = cliente.chat.completions.create.call_args.kwargs
    assert kw["max_tokens"] == 512 and kw["temperature"] == 0.2
    assert (resp.tokens_entrada, resp.tokens_salida) == (120, 7)
    p.completar([{"role": "user", "content": "otra"}])
    assert (p.uso.llamadas, p.uso.tokens_entrada, p.uso.tokens_salida, p.uso.total) == (2, 240, 14, 254)


def test_parametros_por_llamada_sobrescriben_los_defaults(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.return_value = respuesta_falsa()
    crear_proveedor(cfg()).completar([{"role": "user", "content": "hola"}], max_tokens=20)
    assert cliente.chat.completions.create.call_args.kwargs["max_tokens"] == 20


def test_sistema_se_antepone_y_se_recorta_el_historial(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.return_value = respuesta_falsa()
    p = crear_proveedor(cfg(llm_contexto_entrada=400))
    historial = [_msg("user", 900), _msg("assistant", 900), {"role": "user", "content": "¿cuánto cuesta?"}]
    p.completar(historial, sistema=PROMPT_SISTEMA_COTIZACIONES)
    enviados = cliente.chat.completions.create.call_args.kwargs["messages"]
    assert enviados[0] == {"role": "system", "content": PROMPT_SISTEMA_COTIZACIONES}
    assert enviados[-1]["content"] == "¿cuánto cuesta?" and len(enviados) < 4


def test_limites_desactivables(openai_falso):
    _, cliente = openai_falso
    cliente.chat.completions.create.return_value = respuesta_falsa()
    crear_proveedor(cfg(llm_max_tokens_salida=0)).completar([{"role": "user", "content": "hola"}])
    assert "max_tokens" not in cliente.chat.completions.create.call_args.kwargs


def test_prompt_de_dominio_es_corto_y_respeta_las_reglas():
    assert estimar_tokens(PROMPT_SISTEMA_COTIZACIONES) < 400
    assert "No calcules" in PROMPT_SISTEMA_COTIZACIONES and "fuente" in PROMPT_SISTEMA_COTIZACIONES
