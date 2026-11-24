"""Pruebas del medidor de uso (cuota gratuita de OpenRouter). Sin red ni claves reales."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from agent.llm import ConfigLLM, ErrorLimiteLLM, UsoAcumulado
from agent.llm.proveedores import segundos_hasta_reintento, texto_espera
from agent.llm.uso import CuotaOpenRouter, VentanaMinuto, proximo_reinicio_diario
from api import chat as modulo_chat
from api.main import app

CLAVE_FALSA = "sk-or-v1-clave-de-prueba-no-real-abcd1234"
cliente = TestClient(app)


# --------------------------------------------------------------------------- reinicio diario
def test_reinicio_es_el_siguiente_00_utc():
    assert proximo_reinicio_diario(datetime(2026, 11, 24, 3, 15, tzinfo=timezone.utc)) == datetime(2026, 11, 25, tzinfo=timezone.utc)
    # Justo a medianoche UTC ya empezó un día nuevo: el siguiente reinicio es 24 h después, no «ahora».
    assert proximo_reinicio_diario(datetime(2026, 11, 25, 0, 0, tzinfo=timezone.utc)) == datetime(2026, 11, 26, tzinfo=timezone.utc)
    assert proximo_reinicio_diario(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)) == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_reinicio_convierte_otras_zonas_a_utc():
    de_merida = datetime.fromisoformat("2026-11-24T20:00:00-06:00")  # = 02:00 UTC del 25
    assert proximo_reinicio_diario(de_merida) == datetime(2026, 11, 26, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- ventana por minuto
def test_ventana_cuenta_y_libera_en_orden():
    v = VentanaMinuto(ventana_s=60)
    assert v.estado(ahora=0) == (0, None)
    v.registrar(ahora=10)
    v.registrar(ahora=40)
    assert v.estado(ahora=50) == (2, 20)  # la de t=10 sale en t=70
    assert v.estado(ahora=71) == (1, 29)  # salió la primera; la de t=40 sale en t=100
    assert v.estado(ahora=100) == (0, None)


# --------------------------------------------------------------------------- cuota de OpenRouter
def respuesta_key(**extra):
    datos = {
        "label": f"sk-or-v1-{CLAVE_FALSA[-6:]}", "is_free_tier": True, "usage": 0,
        "free_model_daily_requests": {"used": 12, "limit": 50, "remaining": 38}, **extra,
    }
    return httpx.Response(200, json={"data": datos}, request=httpx.Request("GET", "https://x.invalid/key"))


def test_cuota_extrae_lo_necesario_y_descarta_el_label(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: respuesta_key())
    cuota = CuotaOpenRouter().consultar(CLAVE_FALSA)
    assert cuota == {"plan_gratuito": True, "usadas": 12, "limite": 50, "restantes": 38}
    assert "label" not in str(cuota) and "sk-or" not in str(cuota)


def test_cuota_usa_cache_y_se_puede_invalidar(monkeypatch):
    llamadas = []
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (llamadas.append(1), respuesta_key())[1])
    c = CuotaOpenRouter()
    c.consultar(CLAVE_FALSA)
    c.consultar(CLAVE_FALSA)
    assert len(llamadas) == 1
    c.invalidar()
    c.consultar(CLAVE_FALSA)
    assert len(llamadas) == 2


@pytest.mark.parametrize("falla", [httpx.ConnectError("sin red"), ValueError("json roto")])
def test_cuota_devuelve_none_si_falla(monkeypatch, falla):
    def explota(*a, **k):
        raise falla
    monkeypatch.setattr(httpx, "get", explota)
    assert CuotaOpenRouter().consultar(CLAVE_FALSA) is None


def test_cuota_devuelve_none_con_401(monkeypatch):
    sin_permiso = httpx.Response(401, json={"error": "no"}, request=httpx.Request("GET", "https://x.invalid/key"))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: sin_permiso)
    assert CuotaOpenRouter().consultar(CLAVE_FALSA) is None


# --------------------------------------------------------------------------- 429 con tiempo de espera
def error_429(cabeceras=None):
    req = httpx.Request("POST", "https://ejemplo.invalid/chat/completions")
    return openai.RateLimitError("límite", response=httpx.Response(429, request=req, headers=cabeceras or {}), body=None)


def test_espera_desde_retry_after():
    assert segundos_hasta_reintento(error_429({"Retry-After": "42"})) == 42


def test_espera_desde_x_ratelimit_reset_en_milisegundos():
    ahora = 1_000_000.0
    assert segundos_hasta_reintento(error_429({"X-RateLimit-Reset": str(int((ahora + 90) * 1000))}), ahora=ahora) == 90


def test_espera_ausente_o_ilegible_es_none():
    assert segundos_hasta_reintento(error_429()) is None
    assert segundos_hasta_reintento(error_429({"Retry-After": "pronto"})) is None
    assert segundos_hasta_reintento(ValueError("no es un error de openai")) is None


def test_espera_nunca_es_menor_a_un_segundo():
    ahora = time.time()
    assert segundos_hasta_reintento(error_429({"X-RateLimit-Reset": str(int((ahora - 50) * 1000))}), ahora=ahora) == 1


@pytest.mark.parametrize("segundos,texto", [(45, "45 s"), (600, "10 min"), (3600, "1 h"), (12000, "3 h 20 min")])
def test_texto_espera(segundos, texto):
    assert texto_espera(segundos) == texto


def test_el_error_traducido_trae_la_espera(monkeypatch):
    from agent.llm import crear_proveedor
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    prov = crear_proveedor(ConfigLLM(_env_file=None, llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/b:free"))
    err = prov._traducir(error_429({"Retry-After": "120"}))
    assert isinstance(err, ErrorLimiteLLM) and err.reintentar_en_s == 120
    assert "2 min" in str(err) and "por peticiones" in str(err) and CLAVE_FALSA not in str(err)


# --------------------------------------------------------------------------- GET /api/chat/uso
@pytest.fixture
def entorno(monkeypatch):
    for v in ("LLM_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODELS", "OLLAMA_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(modulo_chat, "_proveedores", {})
    monkeypatch.setattr(modulo_chat, "_minuto", VentanaMinuto())
    monkeypatch.setattr(modulo_chat, "_cuota", CuotaOpenRouter())

    def configurar(**kw):
        monkeypatch.setattr(modulo_chat, "ConfigLLM", lambda: ConfigLLM(_env_file=None, **kw))
    return configurar


def test_uso_openrouter_con_cuota(entorno, monkeypatch):
    entorno(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/b:free")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: respuesta_key())
    modulo_chat._minuto.registrar()
    modulo_chat._proveedores["texto"] = SimpleNamespace(uso=UsoAcumulado(llamadas=3, tokens_entrada=1000, tokens_salida=250))
    r = cliente.get("/api/chat/uso")
    cuerpo = r.json()
    assert r.status_code == 200 and cuerpo["tipo_limite"] == "peticiones" and cuerpo["plan_gratuito"] is True
    assert cuerpo["dia"] == {"usadas": 12, "limite": 50, "restantes": 38}
    assert cuerpo["reinicio_dia_utc"].endswith("T00:00:00Z") and cuerpo["reinicio_modo"] == "dia_utc"
    assert cuerpo["minuto"]["limite"] == 20 and cuerpo["minuto"]["usadas_aqui"] == 1
    assert cuerpo["sesion"] == {"llamadas": 3, "tokens_entrada": 1000, "tokens_salida": 250, "tokens_total": 1250}
    assert CLAVE_FALSA not in r.text and "label" not in r.text


def test_uso_openrouter_sin_poder_consultar_la_cuota(entorno, monkeypatch):
    entorno(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/b:free")
    def sin_red(*a, **k):
        raise httpx.ConnectError("sin red")
    monkeypatch.setattr(httpx, "get", sin_red)
    cuerpo = cliente.get("/api/chat/uso").json()
    assert cuerpo["dia"] is None and cuerpo["reinicio_dia_utc"] is None and "No se pudo consultar" in cuerpo["aviso"]
    assert cuerpo["minuto"] is not None  # la estimación local sigue disponible


def test_uso_openrouter_sin_clave_no_llama_a_la_red(entorno, monkeypatch):
    entorno(llm_provider="openrouter", openrouter_models="a/b:free")
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("no debe consultar sin clave"))
    assert cliente.get("/api/chat/uso").json()["dia"] is None


def test_uso_ollama_no_tiene_limite(entorno):
    entorno(llm_provider="ollama")
    cuerpo = cliente.get("/api/chat/uso").json()
    assert cuerpo["tipo_limite"] == "ninguno" and cuerpo["dia"] is None and cuerpo["minuto"] is None
    assert "sin límite" in cuerpo["aviso"].lower() or "no hay límite" in cuerpo["aviso"].lower()


# --------------------------------------------------------------------------- POST /api/chat con 429
def test_chat_429_devuelve_retry_after_y_cuenta_la_peticion(entorno, monkeypatch):
    entorno(llm_provider="openrouter", openrouter_api_key=CLAVE_FALSA, openrouter_models="a/b:free")

    class Proveedor:
        nombre = "falso"
        uso = UsoAcumulado()

        def completar(self, *a, **k):
            raise ErrorLimiteLLM("429: límite", reintentar_en_s=75)

    monkeypatch.setattr(modulo_chat, "_obtener_proveedor", lambda vision: Proveedor())
    r = cliente.post("/api/chat", data={"mensaje": "hola", "historial": "[]"})
    assert r.status_code == 429 and r.headers["retry-after"] == "75"
    assert modulo_chat._minuto.estado()[0] == 1  # la petición fallida también gastó cuota
