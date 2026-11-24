"""Totales de referencia para la evaluación, calculados de forma INDEPENDIENTE de `agent/tools`.

Solo usa `csv` y `Decimal` sobre los archivos sintéticos crudos (`data/synthetic/`). No importa nada del agente ni
de la ingesta, para que un error en esos módulos no pueda repetirse aquí y pasar desapercibido.

Uso:
    python eval/referencia.py --actualizar     # recalcula el bloque «esperado» de data/eval/casos.json
"""

from __future__ import annotations

import csv
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SINTETICOS = RAIZ / "data" / "synthetic"
CASOS = RAIZ / "data" / "eval" / "casos.json"
MARGENES = {"economico": Decimal("0.12"), "recomendado": Decimal("0.18"), "premium": Decimal("0.25")}
CENTAVO = Decimal("0.01")


def _texto(ruta: Path) -> str:
    crudo = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return crudo.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {ruta}")


def _precio(texto: str) -> Decimal | None:
    """«$ 1,150.00 MXN», «1250.0 MXN», «1650» → Decimal. Negativos y no numéricos → None."""
    limpio = re.sub(r"[^\d.\-]", "", texto.replace(",", ""))
    if not re.fullmatch(r"\d+(\.\d+)?", limpio):
        return None
    return Decimal(limpio)


def _filas(ruta: Path) -> list[dict]:
    return list(csv.DictReader(_texto(ruta).splitlines()))


def costos_catalogo() -> dict[str, Decimal]:
    """SKU → precio de catálogo en pesos (el costo del Hito 2). Filas sin SKU o con precio inválido se omiten."""
    costos: dict[str, Decimal] = {}
    for fila in _filas(SINTETICOS / "catalogo_materiales.csv"):
        sku = (fila.get("SKU") or "").strip()
        precio = _precio(fila.get("Precio_Unitario") or "")
        if sku and precio is not None and sku not in costos:
            costos[sku] = precio
    return costos


def servicios_tarifario() -> dict[str, dict]:
    """Código → {precio, incluir_en}."""
    salida: dict[str, dict] = {}
    for fila in _filas(SINTETICOS / "tarifario_servicios.csv"):
        codigo = (fila.get("Codigo") or "").strip()
        precio = _precio(fila.get("Precio_Unitario") or "")
        if codigo and precio is not None:
            salida[codigo] = {"precio": precio, "incluir_en": (fila.get("Incluir_En") or "todos").strip().lower()}
    return salida


def totales_esperados(renglones: list[dict], servicios: list[dict]) -> dict[str, dict]:
    """Subtotal, IVA y total por escenario, en centavos enteros. Los opcionales «premium» del tarifario entran solo al premium."""
    catalogo = costos_catalogo()
    tarifario = servicios_tarifario()
    lineas = [(catalogo[r["sku"]], r["cantidad"], "todos") for r in renglones]
    lineas += [(tarifario[s["codigo"]]["precio"], s["cantidad"], tarifario[s["codigo"]]["incluir_en"]) for s in servicios]
    lineas += [(t["precio"], 1, "premium") for t in tarifario.values() if t["incluir_en"] == "premium"]

    salida = {}
    for escenario, margen in MARGENES.items():
        subtotal = Decimal(0)
        for costo, cantidad, incluir in lineas:
            if incluir == "premium" and escenario != "premium":
                continue
            precio = (costo / (1 - margen)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
            subtotal += precio * cantidad
        iva = (subtotal * Decimal("0.16")).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        salida[escenario] = {
            "subtotal_centavos": int(subtotal * 100),
            "iva_centavos": int(iva * 100),
            "total_centavos": int((subtotal + iva) * 100),
        }
    return salida


def actualizar_casos() -> int:
    datos = json.loads(CASOS.read_text(encoding="utf-8"))
    for caso in datos["casos"]:
        caso["esperado"] = totales_esperados(caso["renglones"], caso["servicios"])
    CASOS.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(datos["casos"])


if __name__ == "__main__":
    if "--actualizar" in sys.argv:
        print(f"Totales esperados recalculados para {actualizar_casos()} casos en {CASOS}")
    else:
        print(__doc__)
