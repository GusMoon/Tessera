"""Orquestador: encadena las herramientas (código) y deja que el LLM **solo redacte** notas y riesgos.

- Las herramientas las encadena el código, no el modelo: un modelo pequeño no es fiable para tool calling y eso
  no se midió en el Hito 2.
- Regla 1: el LLM no calcula. Todo número de su texto debe existir en el contexto que se le entregó (la salida de
  las herramientas); si no, su texto se descarta y se avisa.
- Ante cualquier fallo del modelo (límite, red, JSON roto) se devuelve el resultado determinista sin redacción.
- `MODO_DEMO=true` sustituye el paso del LLM por `agent/demo/respuestas.json`; los demás pasos siguen reales.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from agent import bitacora
from agent.cotizar import cotizar
from agent.llm import PROMPT_SISTEMA_COTIZACIONES, ConfigLLM, ErrorLLM, ProveedorLLM
from agent.memory import memoria
from agent.tools.calcular_cotizacion import ESCENARIOS
from retrieval.indice import Indice

RUTA_DEMO = Path(__file__).resolve().parent / "demo" / "respuestas.json"
INSTRUCCION_REDACCION = (
    "Redacta para cada escenario (economico, recomendado, premium) una nota breve (máx. 2 frases) y hasta 2 riesgos. "
    "Responde SOLO con JSON: {\"economico\": {\"notas\": \"...\", \"riesgos\": [\"...\"]}, \"recomendado\": {...}, \"premium\": {...}}. "
    "No calcules ni escribas ninguna cifra que no aparezca en el contexto."
)


def pesos(centavos: int) -> str:
    return f"${centavos / 100:,.2f} MXN"


# --------------------------------------------------------------------------- validación de cifras
def _numeros(texto: str) -> set[str]:
    salida = set()
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", texto):
        try:
            salida.add(format(Decimal(m.replace(",", "")).normalize(), "f"))
        except InvalidOperation:
            continue
    return salida


def cifras_no_respaldadas(texto: str, contexto: str) -> set[str]:
    """Números del `texto` que NO aparecen en el `contexto` entregado al modelo."""
    return _numeros(texto) - _numeros(contexto)


# --------------------------------------------------------------------------- contexto para el modelo
def construir_contexto(resultado: dict, hechos: list[dict]) -> str:
    lineas = [f"Solicitud: {resultado['solicitud']}"]
    for esc in ESCENARIOS:
        e = resultado["escenarios"][esc]
        lineas.append(f"\nEscenario {esc} (margen {e['margen_objetivo_puntos_base'] / 100:g} %): total {pesos(e['total_centavos'])}")
        for p in e["partidas"]:
            antiguo = f", precio de {p['antiguedad_meses']} meses de antigüedad" if p["precio_antiguo"] else ""
            lineas.append(f"- {p['cantidad']} {p['unidad']} {p['concepto']} a {pesos(p['precio_unitario_centavos'])} [{p['fuente_ref']}]{antiguo}")
    for aviso in resultado["avisos"]:
        lineas.append(f"Aviso: {aviso}")
    if hechos:
        lineas.append("\nMemoria confirmada por el equipo:")
        lineas += [f"- {h['texto']} (origen: {h['origen']})" for h in hechos]
    return "\n".join(lineas)


def _redaccion_determinista(resultado: dict) -> dict:
    salida = {}
    for esc in ESCENARIOS:
        antiguos = sum(1 for p in resultado["escenarios"][esc]["partidas"] if p["precio_antiguo"])
        riesgos = [f"{antiguos} partida(s) con precio de más de 6 meses de antigüedad."] if antiguos else []
        salida[esc] = {"notas": "", "riesgos": riesgos}
    return salida


def _leer_json(texto: str) -> dict:
    limpio = texto.strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        raise ValueError("el modelo no devolvió JSON")
    datos = json.loads(m.group(0))
    salida = {}
    for esc in ESCENARIOS:
        bloque = datos.get(esc) or {}
        salida[esc] = {"notas": str(bloque.get("notas", "")).strip(),
                       "riesgos": [str(r).strip() for r in (bloque.get("riesgos") or []) if str(r).strip()][:2]}
    return salida


# --------------------------------------------------------------------------- orquestación
def orquestar(
    solicitud: str,
    usuario_id: str,
    conn: sqlite3.Connection,
    indice: Indice,
    proveedor: ProveedorLLM | None = None,
    modo_demo: bool | None = None,
    registrar_bitacora: bool = True,
) -> dict:
    inicio = time.perf_counter()
    resultado = cotizar(solicitud, usuario_id, conn, indice)
    redaccion = {"origen": "determinista", "modelo": None, "latencia_s": 0.0, "aviso": None, "escenarios": None}

    if resultado["estado"] == "completa":
        redaccion["escenarios"] = _redaccion_determinista(resultado)
        demo = ConfigLLM().modo_demo if modo_demo is None else modo_demo
        if demo:
            try:
                datos = json.loads(RUTA_DEMO.read_text(encoding="utf-8"))["escenarios"]
                redaccion.update(origen="demo", escenarios=_leer_json(json.dumps(datos)))
            except (OSError, ValueError, KeyError) as exc:
                redaccion["aviso"] = f"No se pudo leer la respuesta de demostración ({exc}); se usó la redacción básica."
        elif proveedor is not None:
            contexto = construir_contexto(resultado, memoria.para_contexto(conn))
            try:
                r = proveedor.completar(
                    [{"role": "user", "content": f"{contexto}\n\n{INSTRUCCION_REDACCION}"}], sistema=PROMPT_SISTEMA_COTIZACIONES
                )
                texto_modelo = _leer_json(r.texto)
                inventadas = cifras_no_respaldadas(json.dumps(texto_modelo, ensure_ascii=False), contexto)
                if inventadas:
                    redaccion["aviso"] = ("Se descartó el texto del modelo porque tenía cifras que no salen de las herramientas: "
                                          + ", ".join(sorted(inventadas)) + ".")
                else:
                    redaccion.update(origen="llm", modelo=r.modelo, latencia_s=round(r.latencia_s, 2), escenarios=texto_modelo)
            except (ErrorLLM, ValueError) as exc:
                redaccion["aviso"] = f"El modelo no pudo redactar ({exc}); se muestra el resultado calculado sin redacción."
    resultado["redaccion"] = redaccion

    herramientas = ["interpretar", "buscar_precios", "buscar_historial"]
    if resultado["estado"] == "completa":
        herramientas.append("calcular_cotizacion")
    if redaccion["origen"] in ("llm", "demo"):
        herramientas.append(f"redaccion:{redaccion['origen']}")
    resultado["herramientas"] = herramientas
    resultado["duracion_ms"] = int((time.perf_counter() - inicio) * 1000)
    if registrar_bitacora:
        registrar_en_bitacora(conn, usuario_id, resultado)
    return resultado


def registrar_en_bitacora(conn: sqlite3.Connection, usuario_id: str, resultado: dict) -> int:
    """Anota la solicitud en la bitácora (qué se pidió, qué fuentes y herramientas, cuánto tardó) y devuelve su id."""
    resultado["bitacora_id"] = bitacora.registrar(
        conn, usuario_id, resultado["solicitud"], [f["ref"] for f in resultado["fuentes"]], resultado["herramientas"], resultado["duracion_ms"]
    )
    return resultado["bitacora_id"]
