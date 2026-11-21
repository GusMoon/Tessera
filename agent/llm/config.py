"""Configuración del proveedor de LLM, cargada desde variables de entorno y `.env`.

La validación específica de cada proveedor (clave presente, modelos ``:free``) se hace
al crearlo (`crear_proveedor`), no al cargar la configuración: con ``LLM_PROVIDER=ollama``
los valores de OpenRouter pueden estar vacíos sin que eso sea un error.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPO = Path(__file__).resolve().parents[2]


class ConfigLLM(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_REPO / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # `VARIABLE=` vacía en .env equivale a "no definida" (usa el valor por defecto)
        extra="ignore",
    )

    llm_provider: str = "ollama"  # "ollama" | "openrouter"; se valida en `crear_proveedor` con mensaje claro

    # SecretStr: su repr/str es '**********', así que no se filtra por accidente a logs o tracebacks.
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_models: str = ""  # lista separada por comas; se interpreta con `modelos_openrouter`
    openrouter_referer: str = ""
    openrouter_title: str = "Tessera"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:3b-instruct"

    # Gestión de tokens. Valores conservadores: Ollama suele usar un contexto de ~4096 tokens
    # [Probable], y en los modelos gratuitos el límite de uso se gasta por petición y por token.
    llm_max_tokens_salida: int = 512  # tope de la respuesta; 0 = sin tope
    llm_temperatura: float = 0.2  # baja: respuestas estables y menos divagación en cotizaciones
    llm_contexto_entrada: int = 3000  # tokens estimados de historial a enviar; 0 = no recortar

    modo_demo: bool = False  # solo se lee; el modo demo aún no está implementado

    @property
    def modelos_openrouter(self) -> list[str]:
        """``OPENROUTER_MODELS`` como lista: separa por comas, recorta espacios, ignora vacíos."""
        return [m.strip() for m in self.openrouter_models.split(",") if m.strip()]
