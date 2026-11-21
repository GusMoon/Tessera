"""Verifica la configuración del LLM enviando una pregunta sintética de prueba.

Uso (desde la raíz del repositorio, con el entorno virtual activo):
    python scripts/verificar_llm.py

El proveedor sale de LLM_PROVIDER (predeterminado: ollama) y el resto de .env.
Código de salida: 0 = APROBADO, 1 = FALLIDO. Nunca imprime la clave.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite `import agent` al ejecutar por ruta

from agent.llm import ConfigLLM, ErrorLLM, crear_proveedor  # noqa: E402

PREGUNTA = "Responde solo con la palabra OK"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        config = ConfigLLM()
        print(f"Proveedor configurado: {config.llm_provider}")
        proveedor = crear_proveedor(config)
        print(f"Modelos configurados:  {', '.join(proveedor.modelos)}")
        print(f"Pregunta de prueba:    {PREGUNTA!r}")
        respuesta = proveedor.completar([{"role": "user", "content": PREGUNTA}], max_tokens=20)
    except ErrorLLM as exc:
        print(f"\nError: {exc}")
        print("Resultado: FALLIDO")
        return 1

    print(f"Modelo que respondió:  {respuesta.modelo}")
    print(f"Latencia:              {respuesta.latencia_s:.2f} s")
    print(f"Tokens (entrada/salida): {respuesta.tokens_entrada} / {respuesta.tokens_salida}")
    print(f"Respuesta:             {respuesta.texto.strip()!r}")
    aprobado = re.search(r"\bok\b", respuesta.texto, re.IGNORECASE) is not None
    print(f"Resultado: {'APROBADO' if aprobado else 'FALLIDO (la respuesta no contiene OK)'}")
    return 0 if aprobado else 1


if __name__ == "__main__":
    raise SystemExit(main())
