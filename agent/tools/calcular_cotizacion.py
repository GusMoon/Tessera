"""Herramienta `calcular_cotizacion` (regla 1 de CLAUDE.md: el modelo no calcula).

Código determinista, solo enteros: los importes viajan en centavos y nunca pasan por punto flotante. Reproduce
exactamente `web/src/lib/calculo.ts` (`divRedondeada`: medio hacia afuera del cero); la paridad se prueba con el
fixture compartido `tests/fixtures/calculo_casos.json`.

Tres escenarios con el mismo costo y distinto margen sobre el precio de venta:
    precio_unitario = costo_unitario / (1 − margen)       (margen en puntos base: 1 800 = 18 %)
Los servicios con `incluir_en = 'premium'` (supervisión, garantía) solo entran al escenario premium.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

ESCENARIOS = ("economico", "recomendado", "premium")
MARGENES_PUNTOS_BASE = {"economico": 1200, "recomendado": 1800, "premium": 2500}
TASA_IVA_PORCIENTO = 16
MESES_PRECIO_ANTIGUO = 6  # «más de 6 meses»: 7 o más meses cumplidos


def div_redondeada(numerador: int, denominador: int) -> int:
    """División entera con redondeo de medio hacia afuera del cero (igual que `divRedondeada` en la interfaz)."""
    if denominador <= 0:
        raise ValueError("El denominador debe ser positivo.")
    signo = -1 if numerador < 0 else 1
    n = abs(numerador)
    return signo * ((2 * n + denominador) // (2 * denominador))


@dataclass(frozen=True)
class Linea:
    """Un renglón a cotizar, con el costo y la fuente de donde sale (regla 2)."""

    tipo: str  # 'material' | 'servicio'
    codigo: str
    concepto: str
    unidad: str
    cantidad: int
    costo_unitario_centavos: int
    fuente_ref: str
    fuente_fecha: str | None = None
    antiguedad_meses: int = 0
    incluir_en: str = "todos"  # 'todos' | 'premium'

    def __post_init__(self) -> None:
        if not isinstance(self.cantidad, int) or isinstance(self.cantidad, bool) or self.cantidad < 1:
            raise ValueError(f"La cantidad de {self.codigo} debe ser un entero mayor o igual a 1.")
        if not isinstance(self.costo_unitario_centavos, int) or self.costo_unitario_centavos < 0:
            raise ValueError(f"El costo de {self.codigo} debe ser un entero de centavos mayor o igual a 0.")
        if not self.fuente_ref:
            raise ValueError(f"{self.codigo} no tiene fuente: toda partida debe citar la suya.")
        if self.incluir_en not in ("todos", "premium"):
            raise ValueError(f"incluir_en no válido en {self.codigo}: {self.incluir_en!r}.")


def precio_con_margen(costo_centavos: int, margen_puntos_base: int) -> int:
    """Precio unitario de venta en centavos para un margen sobre el precio (1 800 = 18 %)."""
    if not 0 <= margen_puntos_base < 10000:
        raise ValueError("El margen debe estar entre 0 y 9 999 puntos base.")
    return div_redondeada(costo_centavos * 10000, 10000 - margen_puntos_base)


def totales(importes: list[int], costos: list[int], tasa_iva_porciento: int = TASA_IVA_PORCIENTO) -> dict:
    """Subtotal, IVA, total, costo y margen a partir de importes y costos por renglón (centavos)."""
    subtotal = sum(importes)
    iva = div_redondeada(subtotal * tasa_iva_porciento, 100)
    costo = sum(costos)
    margen = subtotal - costo
    return {
        "subtotal_centavos": subtotal,
        "iva_centavos": iva,
        "total_centavos": subtotal + iva,
        "costo_centavos": costo,
        "margen_centavos": margen,
        "margen_puntos_base": None if subtotal == 0 else div_redondeada(margen * 10000, subtotal),
    }


def calcular_cotizacion(
    lineas: list[Linea],
    margenes: dict[str, int] | None = None,
    tasa_iva_porciento: int = TASA_IVA_PORCIENTO,
) -> dict:
    """Calcula los tres escenarios. Devuelve `{escenario: {...partidas y totales...}}`; ver `docs/contratos.md`."""
    margenes = margenes or MARGENES_PUNTOS_BASE
    faltan = [e for e in ESCENARIOS if e not in margenes]
    if faltan:
        raise ValueError(f"Faltan márgenes para: {', '.join(faltan)}.")
    repeticiones = Counter(l.codigo for l in lineas)

    resultado: dict[str, dict] = {}
    for escenario in ESCENARIOS:
        partidas = []
        for l in lineas:
            if l.incluir_en == "premium" and escenario != "premium":
                continue
            precio = precio_con_margen(l.costo_unitario_centavos, margenes[escenario])
            partidas.append(
                {
                    "orden": len(partidas) + 1,
                    "tipo": l.tipo,
                    "codigo": l.codigo,
                    "concepto": l.concepto,
                    "unidad": l.unidad,
                    "cantidad": l.cantidad,
                    "costo_unitario_centavos": l.costo_unitario_centavos,
                    "precio_unitario_centavos": precio,
                    "importe_centavos": l.cantidad * precio,
                    "fuente_ref": l.fuente_ref,
                    "fuente_fecha": l.fuente_fecha,
                    "antiguedad_meses": l.antiguedad_meses,
                    "precio_antiguo": l.antiguedad_meses > MESES_PRECIO_ANTIGUO,
                    "duplicada": repeticiones[l.codigo] > 1,
                }
            )
        resultado[escenario] = {
            "escenario": escenario,
            "margen_objetivo_puntos_base": margenes[escenario],
            "partidas": partidas,
            **totales(
                [p["importe_centavos"] for p in partidas],
                [p["cantidad"] * p["costo_unitario_centavos"] for p in partidas],
                tasa_iva_porciento,
            ),
        }
    return resultado
