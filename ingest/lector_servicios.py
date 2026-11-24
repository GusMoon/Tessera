"""Lector y validador del tarifario de servicios (flete, instalación, opcionales premium) en CSV."""

import csv
import io
import sqlite3
from pathlib import Path
from typing import BinaryIO, Union

from ingest.validador import normalizar_fecha, normalizar_moneda, normalizar_unidad

COLUMNAS_TARIFARIO = {"codigo", "servicio", "tipo", "precio_unitario"}
TIPOS = {"flete": "Flete", "instalacion": "Instalación", "instalación": "Instalación", "opcional": "Opcional"}
INCLUIR_EN = {"todos", "premium"}


def es_tarifario(encabezados: list[str]) -> bool:
    """¿Los encabezados del CSV corresponden a un tarifario de servicios (y no a un catálogo)?"""
    return COLUMNAS_TARIFARIO.issubset({h.strip().lower() for h in encabezados if h})


def leer_texto_csv(archivo_o_ruta: Union[str, Path, BinaryIO, io.StringIO, bytes]) -> str:
    """Devuelve el contenido de un CSV como texto, sea ruta, bytes o flujo."""
    if isinstance(archivo_o_ruta, (str, Path)):
        return Path(archivo_o_ruta).read_text(encoding="utf-8-sig")
    contenido = archivo_o_ruta if isinstance(archivo_o_ruta, bytes) else archivo_o_ruta.read()
    return contenido.decode("utf-8-sig", errors="replace") if isinstance(contenido, bytes) else contenido


def procesar_csv_servicios(
    archivo_o_ruta: Union[str, Path, BinaryIO, io.StringIO, bytes],
    fuente_id: int,
    nombre_archivo: str,
    conn: sqlite3.Connection,
) -> dict:
    """Lee, valida y guarda el tarifario. Registra rechazos legibles en 'rechazos'.
    Retorna métricas: {'leidas', 'guardadas', 'rechazadas', 'omitidas'}."""
    leidas = guardadas = rechazadas = 0

    def rechazar(fila_num: int, campo: str, crudo: str, motivo: str) -> None:
        conn.execute(
            """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
            (fuente_id, nombre_archivo, fila_num, campo, crudo, motivo),
        )

    lector = csv.DictReader(io.StringIO(leer_texto_csv(archivo_o_ruta)))
    # Encabezados sin importar mayúsculas ni espacios: «Código » == «codigo»
    for numero_fila, fila_cruda in enumerate(lector, start=2):
        fila = {(k or "").strip().lower(): (v or "").strip() for k, v in fila_cruda.items()}
        leidas += 1

        codigo = fila.get("codigo", "")
        if not codigo:
            rechazar(numero_fila, "Codigo", "", "Código de servicio faltante o vacío")
            rechazadas += 1
            continue
        servicio = fila.get("servicio", "")
        if not servicio:
            rechazar(numero_fila, "Servicio", "", "Descripción del servicio faltante o vacía")
            rechazadas += 1
            continue
        tipo = TIPOS.get(fila.get("tipo", "").lower())
        if tipo is None:
            rechazar(numero_fila, "Tipo", fila.get("tipo", ""), "Tipo de servicio no reconocido")
            rechazadas += 1
            continue
        precio, precio_ok, motivo_precio = normalizar_moneda(fila.get("precio_unitario", ""))
        if not precio_ok:
            rechazar(numero_fila, "Precio_Unitario", fila.get("precio_unitario", ""), motivo_precio)
            rechazadas += 1
            continue
        incluir_en = (fila.get("incluir_en") or "todos").lower()
        if incluir_en not in INCLUIR_EN:
            rechazar(numero_fila, "Incluir_En", fila.get("incluir_en", ""), "Valor de Incluir_En no reconocido")
            rechazadas += 1
            continue

        fecha_iso, antiguedad, fecha_ok, _ = normalizar_fecha(fila.get("fecha_precio", ""))
        conn.execute(
            """INSERT INTO servicios (
                   fuente_id, codigo, servicio, tipo, unidad, precio_unitario, zona, incluir_en,
                   fecha_precio, desactualizado, antiguedad_meses, notas, archivo_origen
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fuente_id, codigo, servicio, tipo, normalizar_unidad(fila.get("unidad", "")), precio,
                fila.get("zona") or None, incluir_en, fecha_iso if fecha_ok else None,
                1 if antiguedad > 6 else 0, antiguedad, fila.get("notas", ""), nombre_archivo,
            ),
        )
        guardadas += 1

    return {"leidas": leidas, "guardadas": guardadas, "rechazadas": rechazadas, "omitidas": 0}
