"""`cotizar`: de una solicitud en lenguaje natural a tres escenarios calculados con sus fuentes.

Camino determinista (sin LLM): interpretar → buscar precios e historial → `calcular_cotizacion`.
Es lo que mide `eval/evaluar.py` para el Hito 2. El LLM, si se usa, solo redacta encima (`agent/orquestador.py`).
"""

from __future__ import annotations

import sqlite3
import time

from agent.interpretar import interpretar
from agent.tools.buscar_historial import buscar_historial
from agent.tools.calcular_cotizacion import calcular_cotizacion
from retrieval.indice import Indice


def cotizar(solicitud: str, usuario_id: str, conn: sqlite3.Connection, indice: Indice, k_historial: int = 5) -> dict:
    t0 = time.perf_counter()
    interp = interpretar(solicitud, conn, indice, usuario_id)
    t1 = time.perf_counter()
    historial = buscar_historial(conn, indice, solicitud, usuario_id, k=k_historial)
    t2 = time.perf_counter()

    salida: dict = {
        "estado": "requiere_aclaracion" if interp.preguntas or not interp.completa else "completa",
        "solicitud": solicitud,
        "cliente": interp.cliente,
        "zona": interp.zona,
        "preguntas": list(interp.preguntas),
        "avisos": list(interp.avisos),
        "renglones": interp.renglones,
        "historial_parecido": historial,
        "escenarios": None,
        "fuentes": [],
    }
    if not interp.preguntas and not interp.completa:
        salida["preguntas"].append("No pude armar una cotización con lo que escribiste. Indica los materiales y sus cantidades.")

    t3 = t2
    if salida["estado"] == "completa":
        escenarios = calcular_cotizacion(interp.lineas)
        t3 = time.perf_counter()
        salida["escenarios"] = escenarios
        vistas: dict[str, dict] = {}
        for l in interp.lineas:
            vistas.setdefault(
                l.fuente_ref,
                {"ref": l.fuente_ref, "fecha": l.fuente_fecha, "antiguedad_meses": l.antiguedad_meses,
                 "precio_antiguo": l.antiguedad_meses > 6, "concepto": l.concepto},
            )
        salida["fuentes"] = list(vistas.values()) + [
            {"ref": h["ref"], "fecha": h["fecha"], "antiguedad_meses": None, "precio_antiguo": h["desactualizado"],
             "concepto": f"Cotización {h['folio']} · {h['cliente']}"}
            for h in historial
        ]
        antiguas = [f["concepto"] for f in vistas.values() if f["precio_antiguo"]]
        if antiguas:
            salida["avisos"].append(f"{len(antiguas)} precio(s) con más de 6 meses de antigüedad: confirma antes de enviar.")

    salida["tiempos_ms"] = {
        "interpretar": round((t1 - t0) * 1000, 1),
        "historial": round((t2 - t1) * 1000, 1),
        "calculo": round((t3 - t2) * 1000, 1),
        "total": round((t3 - t0) * 1000, 1),
    }
    return salida
