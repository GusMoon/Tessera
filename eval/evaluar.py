"""Evaluación del Hito 2 de Tessera sobre los 50 casos de `data/eval/casos.json`.

Mide, con el hardware real y sin promesas:
  1. Latencia de recuperación híbrida + cálculo de 3 escenarios (mediana y p95; meta: mediana < 500 ms).
  2. Exactitud de totales contra `eval/referencia.py` (meta: 50 de 50).
  3. Recuperación: la cotización histórica parecida aparece entre los primeros 5 resultados (meta: ≥ 80 %).
  4. Fuentes: toda respuesta cita al menos una fuente (meta: 100 %).

Usa una base temporal, así que no toca `db/tessera.db`. Imprime APROBADO o FALLIDO y guarda un JSON en
`eval/resultados/` con fecha, embedder y hardware (regla 9: solo se reporta lo medido).

    python eval/evaluar.py                  # embedder e5 (el del plan)
    python eval/evaluar.py --embedder hash  # solo para comprobar el script sin el modelo
    python eval/evaluar.py --con-llm        # además mide la redacción con el LLM de .env (no cuenta para el veredicto)
    python eval/evaluar.py --demo           # además prueba la redacción con MODO_DEMO (respuestas precargadas)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

CASOS = RAIZ / "data" / "eval" / "casos.json"
SINTETICOS = RAIZ / "data" / "synthetic"
RESULTADOS = RAIZ / "eval" / "resultados"
USUARIO = "u1"  # Vendedor: ve fuentes «Todos» y «Comercial»
METAS = {"mediana_ms": 500.0, "exactitud": 50, "top5_pct": 80.0, "fuentes_pct": 100.0}


def memoria_total_gb() -> float | None:
    try:
        import ctypes

        class Estado(ctypes.Structure):
            _fields_ = [("longitud", ctypes.c_ulong), ("carga", ctypes.c_ulong), ("total_fisica", ctypes.c_ulonglong),
                        ("libre_fisica", ctypes.c_ulonglong), ("total_pagina", ctypes.c_ulonglong), ("libre_pagina", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("libre_virtual", ctypes.c_ulonglong), ("libre_ext", ctypes.c_ulonglong)]

        e = Estado()
        e.longitud = ctypes.sizeof(Estado)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))  # type: ignore[attr-defined]
        return round(e.total_fisica / 1024**3, 1)
    except Exception:  # noqa: BLE001 - solo informativo; en otros sistemas se omite
        return None


def hardware() -> dict:
    return {"procesador": platform.processor() or platform.machine(), "nucleos": os.cpu_count(), "ram_gb": memoria_total_gb(),
            "sistema": platform.platform(), "python": platform.python_version()}


def percentil(valores: list[float], p: float) -> float:
    orden = sorted(valores)
    return orden[min(len(orden) - 1, int(round(p / 100 * (len(orden) - 1))))]


def preparar_base(carpeta: Path, embedder) -> dict:
    """Carga el dataset sintético en una base temporal y la indexa. Devuelve tiempos de la carga."""
    os.environ["TESSERA_DB_PATH"] = str(carpeta / "eval.db")
    os.environ["TESSERA_INDEX_DIR"] = str(carpeta / "indice")
    from db.database import get_connection, init_db
    from ingest.servicio import procesar_archivo
    from retrieval.servicio import reindexar

    init_db(reset=True)
    conn = get_connection()
    archivos = [SINTETICOS / "catalogo_materiales.csv", SINTETICOS / "historial_cotizaciones.xlsx", SINTETICOS / "tarifario_servicios.csv",
                *sorted((SINTETICOS / "fichas_tecnicas").glob("*.pdf"))]
    t0 = time.perf_counter()
    for a in archivos:
        procesar_archivo(a, a.name, conn=conn)
    conn.commit()
    t1 = time.perf_counter()
    indexado = reindexar(conn, embedder)
    return {"conn": conn, "segundos_ingesta": round(t1 - t0, 2), "indexado": indexado}


def evaluar_caso(caso: dict, conn, indice) -> dict:
    from agent.cotizar import cotizar

    r = cotizar(caso["solicitud"], USUARIO, conn, indice)
    fila = {"id": caso["id"], "autor": caso["autor"], "estado": r["estado"], "ms": r["tiempos_ms"]["total"],
            "preguntas": r["preguntas"], "exacto": False, "renglones_ok": False, "servicios_ok": False,
            "top5": False, "top1": False, "con_fuentes": False}
    folios = [h["folio"] for h in r["historial_parecido"]]
    fila["top5"] = caso["folio_parecido"] in folios
    fila["top1"] = bool(folios) and folios[0] == caso["folio_parecido"]
    fila["folios_devueltos"] = folios
    if r["escenarios"]:
        fila["exacto"] = all(
            {k: r["escenarios"][e][k] for k in ("subtotal_centavos", "iva_centavos", "total_centavos")} == caso["esperado"][e]
            for e in caso["esperado"]
        )
        partidas = r["escenarios"]["recomendado"]["partidas"]
        obtenidos_m = sorted((p["codigo"], p["cantidad"]) for p in partidas if p["tipo"] == "material")
        esperados_m = sorted((x["sku"], x["cantidad"]) for x in caso["renglones"])
        obtenidos_s = sorted((p["codigo"], p["cantidad"]) for p in partidas if p["tipo"] == "servicio" and p["codigo"] in {x["codigo"] for x in caso["servicios"]})
        esperados_s = sorted((x["codigo"], x["cantidad"]) for x in caso["servicios"])
        fila["renglones_ok"] = obtenidos_m == esperados_m
        fila["servicios_ok"] = obtenidos_s == esperados_s
        if not fila["renglones_ok"]:
            fila["renglones_esperados"], fila["renglones_obtenidos"] = esperados_m, obtenidos_m
        if not fila["servicios_ok"]:
            fila["servicios_esperados"], fila["servicios_obtenidos"] = esperados_s, obtenidos_s
        todas = [p for e in r["escenarios"].values() for p in e["partidas"]]
        fila["con_fuentes"] = bool(r["fuentes"]) and all(p["fuente_ref"] for p in todas)
    return fila


def medir_llm(casos: list[dict], conn, indice, demo: bool, cuantos: int = 3) -> dict:
    """Redacción con el LLM (o MODO_DEMO) en los primeros casos completos. No cuenta para el veredicto del Hito 2."""
    from agent.llm import ErrorLLM, crear_proveedor
    from agent.orquestador import orquestar

    proveedor = None
    if not demo:
        try:
            proveedor = crear_proveedor()
        except ErrorLLM as exc:
            return {"disponible": False, "motivo": str(exc)}
    filas = []
    for caso in casos[:cuantos]:
        t0 = time.perf_counter()
        r = orquestar(caso["solicitud"], USUARIO, conn, indice, proveedor=proveedor, modo_demo=demo, registrar_bitacora=False)
        filas.append({"id": caso["id"], "origen": r["redaccion"]["origen"], "segundos": round(time.perf_counter() - t0, 2), "aviso": r["redaccion"]["aviso"]})
    return {"disponible": True, "modo": "demo" if demo else "llm", "casos": filas}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embedder", choices=["e5", "hash"], default=None)
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--con-llm", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--sin-guardar", action="store_true")
    args = ap.parse_args()

    datos = json.loads(args.casos.read_text(encoding="utf-8"))
    casos = datos["casos"]
    print("=" * 72)
    print(" EVALUACIÓN · HITO 2 · PROCESO (recuperación híbrida + cálculo de escenarios)")
    print("=" * 72)
    print(f"Casos: {len(casos)} ({datos.get('nota', '')[:60]}…)")

    from retrieval.embeddings import crear_embedder
    from retrieval.servicio import obtener_indice

    t0 = time.perf_counter()
    embedder = crear_embedder(args.embedder)
    segundos_modelo = round(time.perf_counter() - t0, 2)
    print(f"Embedder: {embedder.nombre} (carga: {segundos_modelo} s)")

    with tempfile.TemporaryDirectory(prefix="tessera_eval_") as tmp:
        base = preparar_base(Path(tmp), embedder)
        conn = base["conn"]
        print(f"Ingesta del dataset sintético: {base['segundos_ingesta']} s · "
              f"{base['indexado']['fragmentos']} fragmentos indexados en {base['indexado']['segundos_vectores']} s")
        indice = obtener_indice(conn, embedder)
        n_folios = conn.execute("SELECT COUNT(*) FROM cotizaciones_historicas").fetchone()[0]
        filas = [evaluar_caso(c, conn, indice) for c in casos]
        extra_llm = medir_llm(casos, conn, indice, demo=False) if args.con_llm else None
        extra_demo = medir_llm(casos, conn, indice, demo=True) if args.demo else None
        conn.close()

    tiempos = [f["ms"] for f in filas]
    n = len(filas)
    resumen = {
        "mediana_ms": round(statistics.median(tiempos), 1),
        "p95_ms": round(percentil(tiempos, 95), 1),
        "primer_caso_ms": tiempos[0],
        "maximo_ms": round(max(tiempos), 1),
        "exactitud": sum(f["exacto"] for f in filas),
        "renglones_correctos": sum(f["renglones_ok"] for f in filas),
        "servicios_correctos": sum(f["servicios_ok"] for f in filas),
        "completas": sum(f["estado"] == "completa" for f in filas),
        "top5": sum(f["top5"] for f in filas),
        "top1": sum(f["top1"] for f in filas),
        "con_fuentes": sum(f["con_fuentes"] for f in filas),
    }
    resumen["top5_pct"] = round(100 * resumen["top5"] / n, 1)
    resumen["top1_pct"] = round(100 * resumen["top1"] / n, 1)
    resumen["fuentes_pct"] = round(100 * resumen["con_fuentes"] / n, 1)

    criterios = [
        ("Latencia mediana (recuperación + cálculo)", f"{resumen['mediana_ms']} ms (p95 {resumen['p95_ms']} ms, máx {resumen['maximo_ms']} ms)",
         f"< {METAS['mediana_ms']:.0f} ms", resumen["mediana_ms"] < METAS["mediana_ms"]),
        ("Exactitud de totales", f"{resumen['exactitud']} de {n}", f"{METAS['exactitud']} de {n}", resumen["exactitud"] == n),
        ("Cotización parecida en el top-5", f"{resumen['top5']} de {n} ({resumen['top5_pct']} %; top-1: {resumen['top1_pct']} %)",
         f"≥ {METAS['top5_pct']:.0f} %", resumen["top5_pct"] >= METAS["top5_pct"]),
        ("Respuestas con al menos una fuente", f"{resumen['con_fuentes']} de {n} ({resumen['fuentes_pct']} %)", "100 %", resumen["fuentes_pct"] >= METAS["fuentes_pct"]),
    ]
    print("\nResultados")
    print("-" * 72)
    for nombre, medido, meta, ok in criterios:
        print(f"[{'OK ' if ok else 'FALLA'}] {nombre}: {medido}  (meta {meta})")
    print("-" * 72)
    print(f"Diagnóstico: renglones correctos {resumen['renglones_correctos']}/{n} · servicios correctos {resumen['servicios_correctos']}/{n} · "
          f"solicitudes completas {resumen['completas']}/{n}")

    malos = [f for f in filas if not (f["exacto"] and f["top5"] and f["con_fuentes"])]
    if malos:
        print("\nCasos con diferencias:")
        for f in malos:
            print(f"  {f['id']} ({f['autor']}): estado={f['estado']} exacto={f['exacto']} top5={f['top5']} fuentes={f['con_fuentes']}")
            for q in f["preguntas"]:
                print(f"      pregunta: {q}")
            for clave in ("renglones_esperados", "renglones_obtenidos", "servicios_esperados", "servicios_obtenidos"):
                if clave in f:
                    print(f"      {clave}: {f[clave]}")

    for titulo, extra in (("LLM", extra_llm), ("MODO_DEMO", extra_demo)):
        if extra:
            print(f"\nRedacción ({titulo}), fuera del veredicto:")
            if not extra["disponible"]:
                print(f"  no disponible: {extra['motivo']}")
            else:
                for c in extra["casos"]:
                    print(f"  {c['id']}: origen={c['origen']} {c['segundos']} s" + (f" · {c['aviso']}" if c["aviso"] else ""))

    aprobado = all(c[3] for c in criterios)
    print("\n" + "=" * 72)
    print(f" VEREDICTO HITO 2: {'APROBADO' if aprobado else 'FALLIDO'}")
    print("=" * 72)
    print(f"Nota: los 50 casos son un borrador de Claude pendiente de revisión por el equipo (se usaron mientras se desarrolló el "
          f"intérprete: no son un conjunto reservado), y el historial solo tiene {n_folios} folios, varios casi idénticos: el top-5 es orientativo.")

    if not args.sin_guardar:
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        etiqueta = "".join(c if c.isalnum() else "-" for c in embedder.nombre.split("/")[-1])
        ruta = RESULTADOS / f"{date.today().isoformat()}_{etiqueta}.json"
        ruta.write_text(
            json.dumps(
                {"fecha": date.today().isoformat(), "hito": 2, "embedder": embedder.nombre, "segundos_carga_modelo": segundos_modelo,
                 "hardware": hardware(), "metas": METAS, "resumen": resumen, "aprobado": aprobado,
                 "criterios": [{"nombre": c[0], "medido": c[1], "meta": c[2], "ok": c[3]} for c in criterios],
                 "casos": filas, "llm": extra_llm, "demo": extra_demo,
                 "advertencia": f"Casos redactados por Claude (borrador) y usados durante el desarrollo del intérprete, no reservados; historial de {n_folios} folios con varios casi idénticos."},
                ensure_ascii=False, indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"Resultado guardado en {ruta.relative_to(RAIZ)}")
    return 0 if aprobado else 1


if __name__ == "__main__":
    sys.exit(main())
