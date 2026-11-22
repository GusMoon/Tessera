"""Banco de pruebas del LLM por terminal: conversación, archivos (txt, CSV, Excel, PDF) e imágenes.

Uso (desde la raíz del repositorio, con el entorno virtual activo):
    python scripts/probar_llm.py                                  # chat interactivo
    python scripts/probar_llm.py -a data/synthetic/fichas_tecnicas/ficha_02_cable_thw_12.pdf
    python scripts/probar_llm.py -a catalogo.csv -p "¿Qué materiales cuestan más de $500?"   # una sola pregunta
    python scripts/probar_llm.py --proveedor openrouter --modelo google/gemma-4-26b-a4b-it:free -a foto.jpg

Dentro del chat escribe /ayuda. Código de salida (modo -p): 0 = respondió, 1 = error.
Nunca imprime la clave. Solo para pruebas con datos sintéticos o públicos (regla 7 de CLAUDE.md).
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite `import agent` al ejecutar por ruta

from agent.llm import (  # noqa: E402
    PROMPT_SISTEMA_COTIZACIONES,
    ConfigLLM,
    ErrorLLM,
    ErrorModeloNoDisponibleLLM,
    ProveedorLLM,
    crear_proveedor,
)
from agent.llm.adjuntos import Adjunto, ErrorAdjunto, construir_contenido, leer_adjunto  # noqa: E402

AYUDA = """\
Comandos:
  /archivo <ruta>   adjunta un archivo al próximo mensaje (txt, md, json, csv, xlsx, pdf, png, jpg, webp, gif)
  /adjuntos         lista lo adjuntado y pendiente de enviar
  /quitar           descarta los adjuntos pendientes
  /limpiar          borra el historial de la conversación (empieza de cero)
  /sistema          activa/desactiva el prompt de sistema de Tessera (ahora: {sistema})
  /uso              tokens acumulados de esta sesión
  /salir            termina (también Ctrl+C)
Cualquier otra línea se envía como mensaje, con los adjuntos pendientes."""


def modelo_acepta_imagenes(modelo_id: str) -> bool | None:
    """Consulta el catálogo público de OpenRouter (sin clave ni datos del usuario). None = no se pudo saber."""
    try:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=10) as r:
            catalogo = json.load(r)["data"]
    except Exception:
        return None
    for m in catalogo:
        if m.get("id") == modelo_id:
            return "image" in (m.get("architecture", {}).get("input_modalities") or [])
    return None


def avisar_si_no_hay_vision(proveedor: ProveedorLLM) -> None:
    if proveedor.nombre != "openrouter":
        print("  (Ollama: la imagen solo funciona con un modelo de visión, p. ej. llava o qwen2.5vl.)")
        return
    if modelo_acepta_imagenes(proveedor.modelos[0]) is False:
        print(
            f"  AVISO: {proveedor.modelos[0]} solo acepta texto; la imagen será rechazada o ignorada. "
            "Usa --modelo con uno que acepte imágenes (p. ej. google/gemma-4-26b-a4b-it:free)."
        )


def enviar(
    proveedor: ProveedorLLM,
    historial: list[dict],
    pregunta: str,
    adjuntos: list[Adjunto],
    usar_sistema: bool,
    max_tokens: int | None,
) -> bool:
    """Envía un turno. Agrega al historial solo si hubo respuesta. Devuelve True si respondió."""
    historial.append({"role": "user", "content": construir_contenido(pregunta, adjuntos)})
    parametros = {"max_tokens": max_tokens} if max_tokens else {}
    try:
        r = proveedor.completar(historial, sistema=PROMPT_SISTEMA_COTIZACIONES if usar_sistema else None, **parametros)
    except ErrorLLM as exc:
        historial.pop()
        print(f"\nError: {exc}")
        if isinstance(exc, ErrorModeloNoDisponibleLLM) and any(a.tipo == "imagen" for a in adjuntos):
            print("  Si enviaste una imagen, confirma que el modelo acepta imágenes (ver --modelo).")
        return False
    texto = r.texto.strip()
    if not texto:
        print(
            "\n(La respuesta llegó vacía. Con modelos de razonamiento, como ERNIE, el razonamiento consume "
            f"max_tokens antes de responder; reintenta con --max-tokens {max(2048, (max_tokens or 512) * 4)}.)"
        )
        historial.pop()
    else:
        historial.append({"role": "assistant", "content": texto})
        print(f"\n{texto}")
    print(
        f"\n[{r.modelo} · {r.latencia_s:.2f} s · tokens entrada/salida: {r.tokens_entrada}/{r.tokens_salida}]"
    )
    return bool(texto)


def adjuntar(ruta: str, pendientes: list[Adjunto], proveedor: ProveedorLLM) -> None:
    try:
        a = leer_adjunto(ruta)
    except ErrorAdjunto as exc:
        print(f"  No se adjuntó: {exc}")
        return
    pendientes.append(a)
    print(f"  Adjunto listo: {a.resumen}")
    if a.tipo == "imagen":
        avisar_si_no_hay_vision(proveedor)


def parsear_comando(linea: str) -> tuple[str, str]:
    comando, _, resto = linea.partition(" ")
    return comando.lower(), resto.strip()


def chat(proveedor: ProveedorLLM, pendientes: list[Adjunto], usar_sistema: bool, max_tokens: int | None) -> int:
    historial: list[dict] = []
    print(f"Proveedor: {proveedor.nombre} · modelo: {proveedor.modelos[0]} · sistema Tessera: {'sí' if usar_sistema else 'no'}")
    print("Escribe /ayuda para ver los comandos.\n")
    while True:
        try:
            linea = input("tú> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not linea:
            continue
        if linea.startswith("/"):
            comando, resto = parsear_comando(linea)
            if comando in ("/salir", "/exit", "/q"):
                return 0
            elif comando in ("/archivo", "/imagen"):
                if not resto:
                    print("  Uso: /archivo <ruta>")
                for ruta in shlex.split(resto, posix=False) if resto else []:
                    adjuntar(ruta, pendientes, proveedor)
            elif comando == "/adjuntos":
                print("\n".join(f"  - {a.resumen}" for a in pendientes) or "  (ninguno)")
            elif comando == "/quitar":
                pendientes.clear()
                print("  Adjuntos descartados.")
            elif comando == "/limpiar":
                historial.clear()
                print("  Historial borrado.")
            elif comando == "/sistema":
                usar_sistema = not usar_sistema
                print(f"  Prompt de sistema de Tessera: {'activado' if usar_sistema else 'desactivado'}")
            elif comando == "/uso":
                u = proveedor.uso
                print(f"  Llamadas: {u.llamadas} · entrada: {u.tokens_entrada} · salida: {u.tokens_salida} · total: {u.total}")
            elif comando in ("/ayuda", "/help", "/?"):
                print(AYUDA.format(sistema="sí" if usar_sistema else "no"))
            else:
                print("  Comando desconocido. Escribe /ayuda.")
            continue
        if enviar(proveedor, historial, linea, pendientes, usar_sistema, max_tokens):
            pendientes.clear()  # los adjuntos ya viajan en el historial; no se reenvían
        print()


def main() -> int:
    for flujo in (sys.stdout, sys.stdin):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Prueba el LLM por terminal con archivos e imágenes.")
    ap.add_argument("-a", "--archivo", action="append", default=[], metavar="RUTA", help="archivo o imagen a adjuntar (repetible)")
    ap.add_argument("-p", "--pregunta", help="envía una sola pregunta y termina (sin chat)")
    ap.add_argument("--proveedor", choices=("ollama", "openrouter"), help="sobrescribe LLM_PROVIDER")
    ap.add_argument("--modelo", help="sobrescribe el modelo (OPENROUTER_MODELS u OLLAMA_MODEL) solo para esta corrida")
    ap.add_argument("--max-tokens", type=int, help="tope de la respuesta; súbelo si la respuesta llega vacía")
    ap.add_argument("--sin-sistema", action="store_true", help="no antepone el prompt de sistema de Tessera")
    args = ap.parse_args()

    try:
        sobrescribe: dict = {}
        if args.proveedor:
            sobrescribe["llm_provider"] = args.proveedor
        config = ConfigLLM(**sobrescribe)
        if args.modelo:
            campo = "openrouter_models" if config.llm_provider.strip().lower() == "openrouter" else "ollama_model"
            config = ConfigLLM(**sobrescribe, **{campo: args.modelo})
        proveedor = crear_proveedor(config)
    except ErrorLLM as exc:
        print(f"Error: {exc}")
        return 1

    pendientes: list[Adjunto] = []
    for ruta in args.archivo:
        adjuntar(ruta, pendientes, proveedor)
    if len(pendientes) < len(args.archivo):
        return 1  # un adjunto pedido explícitamente falló: no se envía una pregunta incompleta

    usar_sistema = not args.sin_sistema
    if args.pregunta:
        ok = enviar(proveedor, [], args.pregunta, pendientes, usar_sistema, args.max_tokens)
        return 0 if ok else 1
    return chat(proveedor, pendientes, usar_sistema, args.max_tokens)


if __name__ == "__main__":
    raise SystemExit(main())
