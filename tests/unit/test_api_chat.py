"""Pruebas de POST /api/chat con un proveedor simulado: sin red, sin claves y sin tocar la base de datos."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from agent.llm import ConfigLLM, ErrorLimiteLLM, ErrorModeloNoDisponibleLLM, RespuestaLLM
from api import chat as modulo_chat
from api.main import app

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"
)

# Sin `with`, TestClient no ejecuta el evento de arranque (no se toca la base de datos).
cliente = TestClient(app)


class ProveedorFalso:
    nombre = "falso"

    def __init__(self, texto="Respuesta de prueba", error=None):
        self.texto, self.error, self.llamadas = texto, error, []

    def completar(self, mensajes, **parametros):
        self.llamadas.append((mensajes, parametros))
        if self.error:
            raise self.error
        return RespuestaLLM(texto=self.texto, modelo="modelo-falso:free", proveedor="falso", latencia_s=0.5, tokens_entrada=10, tokens_salida=5)


@pytest.fixture
def proveedor(monkeypatch):
    falso = ProveedorFalso()
    pedidos = []
    monkeypatch.setattr(modulo_chat, "_obtener_proveedor", lambda vision: (pedidos.append(vision), falso)[1])
    falso.pedidos_vision = pedidos
    return falso


def enviar(mensaje="Hola", historial=None, archivos=()):
    return cliente.post(
        "/api/chat",
        data={"mensaje": mensaje, "historial": json.dumps(historial or [])},
        files=[("archivos", a) for a in archivos],
    )


def test_respuesta_basica(proveedor):
    r = enviar("¿Qué es THW?")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["texto"] == "Respuesta de prueba" and cuerpo["modelo"] == "modelo-falso:free"
    assert cuerpo["tokens_entrada"] == 10 and cuerpo["adjuntos"] == [] and cuerpo["avisos"] == []
    mensajes, parametros = proveedor.llamadas[0]
    assert mensajes == [{"role": "user", "content": "¿Qué es THW?"}]
    assert parametros["sistema"].startswith("Eres el asistente comercial de Tessera")
    assert parametros["max_tokens"] >= 2048
    assert proveedor.pedidos_vision == [False]


def test_historial_se_traduce_a_roles_de_openai(proveedor):
    enviar("y el flete?", historial=[{"rol": "usuario", "texto": "hola"}, {"rol": "tessera", "texto": "buenas"}])
    mensajes, _ = proveedor.llamadas[0]
    assert [m["role"] for m in mensajes] == ["user", "assistant", "user"]


@pytest.mark.parametrize("historial", ["no es json", '{"rol": "usuario"}', '[{"rol": "otro", "texto": "x"}]', '[{"rol": "usuario"}]'])
def test_historial_invalido_da_400(proveedor, historial):
    r = cliente.post("/api/chat", data={"mensaje": "hola", "historial": historial})
    assert r.status_code == 400 and "historial" in r.json()["detail"]


def test_mensaje_vacio_da_400(proveedor):
    assert enviar("   ").status_code == 400


def test_archivo_de_texto_viaja_rotulado_y_sin_vision(proveedor):
    r = enviar("¿Precio?", archivos=[("nota.txt", b"Cemento $245.00 MXN", "text/plain")])
    assert r.status_code == 200
    assert r.json()["adjuntos"][0]["nombre"] == "nota.txt"
    contenido = proveedor.llamadas[0][0][-1]["content"]
    assert isinstance(contenido, str) and "[ARCHIVO: nota.txt]" in contenido and "Cemento $245.00" in contenido
    assert proveedor.pedidos_vision == [False]


def test_imagen_pide_proveedor_de_vision(proveedor):
    r = enviar("¿Qué ves?", archivos=[("foto.png", PNG_1X1, "image/png")])
    assert r.status_code == 200
    assert proveedor.pedidos_vision == [True]
    partes = proveedor.llamadas[0][0][-1]["content"]
    assert [p["type"] for p in partes] == ["text", "image_url"]


def test_el_nombre_del_archivo_se_limpia_de_rutas(proveedor):
    enviar("x", archivos=[("../../etc/nota.txt", b"hola", "text/plain")])
    assert "[ARCHIVO: nota.txt]" in proveedor.llamadas[0][0][-1]["content"]


def test_formato_no_soportado_da_400(proveedor):
    r = enviar("x", archivos=[("virus.exe", b"MZ", "application/octet-stream")])
    assert r.status_code == 400 and "virus.exe" in r.json()["detail"] and not proveedor.llamadas


def test_demasiados_archivos(proveedor):
    r = enviar("x", archivos=[(f"{i}.txt", b"a", "text/plain") for i in range(6)])
    assert r.status_code == 400 and "Máximo" in r.json()["detail"]


def test_aviso_si_el_archivo_se_recorta(proveedor):
    r = enviar("x", archivos=[("grande.txt", b"a" * 20_000, "text/plain")])
    assert any("grande.txt" in a for a in r.json()["avisos"])


def test_respuesta_vacia_avisa(monkeypatch):
    monkeypatch.setattr(modulo_chat, "_obtener_proveedor", lambda vision: ProveedorFalso(texto="  "))
    r = enviar()
    assert r.status_code == 200 and r.json()["texto"] == "" and "vacía" in r.json()["avisos"][0]


@pytest.mark.parametrize("error,estado", [(ErrorLimiteLLM("429: límite"), 429), (ErrorModeloNoDisponibleLLM("sin modelo"), 502)])
def test_errores_del_llm_se_traducen(monkeypatch, error, estado):
    monkeypatch.setattr(modulo_chat, "_obtener_proveedor", lambda vision: ProveedorFalso(error=error))
    r = enviar()
    assert r.status_code == estado and r.json()["detail"] == str(error)


def test_sin_modelo_de_vision_configurado_da_503(monkeypatch):
    for v in ("LLM_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODELS", "OPENROUTER_MODEL_VISION", "OLLAMA_MODEL_VISION"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(modulo_chat, "ConfigLLM", lambda: ConfigLLM(_env_file=None, llm_provider="ollama"))
    monkeypatch.setattr(modulo_chat, "_proveedores", {})
    r = enviar("x", archivos=[("foto.png", PNG_1X1, "image/png")])
    assert r.status_code == 503 and "modelo de visión" in r.json()["detail"]


def test_config_no_expone_la_clave(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-secreta-de-prueba")
    monkeypatch.setenv("OPENROUTER_MODELS", "a/b:free,c/d:free")
    r = cliente.get("/api/chat/config")
    assert r.status_code == 200
    assert r.json()["proveedor"] == "openrouter" and r.json()["modelo"] == "a/b:free"
    assert "secreta" not in r.text
