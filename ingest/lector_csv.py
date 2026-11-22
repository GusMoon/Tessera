"""Lector y validador de catálogo en formato CSV para Tessera."""

import csv
import io
import sqlite3
from pathlib import Path
from typing import Union, BinaryIO

from ingest.validador import normalizar_fecha, normalizar_moneda, normalizar_unidad


def procesar_csv_catalogo(
    archivo_o_ruta: Union[str, Path, BinaryIO, io.StringIO, bytes],
    fuente_id: int,
    nombre_archivo: str,
    conn: sqlite3.Connection
) -> dict:
    """
    Lee, valida y guarda las filas válidas del catálogo CSV en SQLite.
    Registra rechazos legibles en la tabla 'rechazos'.
    Retorna métricas: {'leidas': int, 'guardadas': int, 'rechazadas': int, 'omitidas': int}
    """
    # Manejar diferentes tipos de entrada (ruta, bytes, stream)
    if isinstance(archivo_o_ruta, (str, Path)):
        f = open(archivo_o_ruta, "r", encoding="utf-8-sig")
        debe_cerrar = True
    elif isinstance(archivo_o_ruta, bytes):
        f = io.StringIO(archivo_o_ruta.decode("utf-8-sig", errors="replace"))
        debe_cerrar = False
    elif isinstance(archivo_o_ruta, io.StringIO):
        f = archivo_o_ruta
        debe_cerrar = False
    else:
        # BinaryIO
        contenido = archivo_o_ruta.read()
        if isinstance(contenido, bytes):
            f = io.StringIO(contenido.decode("utf-8-sig", errors="replace"))
        else:
            f = io.StringIO(contenido)
        debe_cerrar = False

    leidas = 0
    guardadas = 0
    rechazadas = 0
    omitidas = 0

    try:
        reader = csv.DictReader(f)
        
        # Fila 1 es el header en el archivo físico, por lo que la primera fila de datos es la 2
        numero_fila = 2
        
        for fila in reader:
            leidas += 1
            
            sku_crudo = fila.get("SKU", "").strip() if fila.get("SKU") else ""
            desc_cruda = fila.get("Descripcion", "").strip() if fila.get("Descripcion") else ""
            cat_cruda = fila.get("Categoria", "").strip() if fila.get("Categoria") else "General"
            unidad_cruda = fila.get("Unidad", "").strip() if fila.get("Unidad") else ""
            precio_crudo = fila.get("Precio_Unitario", "")
            moneda_cruda = fila.get("Moneda", "MXN")
            fecha_cruda = fila.get("Fecha_Precio", "")
            notas_crudas = fila.get("Notas", "")

            # Validación 1: SKU obligatorio
            if not sku_crudo:
                conn.execute(
                    """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                       VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                    (fuente_id, nombre_archivo, numero_fila, "SKU", sku_crudo, "SKU faltante o vacío")
                )
                rechazadas += 1
                numero_fila += 1
                continue

            # Validación 2: Descripción obligatoria
            if not desc_cruda:
                conn.execute(
                    """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                       VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                    (fuente_id, nombre_archivo, numero_fila, "Descripcion", desc_cruda, "Descripción faltante o vacía")
                )
                rechazadas += 1
                numero_fila += 1
                continue

            # Validación 3: Precio unitario
            precio_val, precio_ok, motivo_precio = normalizar_moneda(precio_crudo)
            if not precio_ok:
                conn.execute(
                    """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                       VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                    (fuente_id, nombre_archivo, numero_fila, "Precio_Unitario", str(precio_crudo), motivo_precio)
                )
                rechazadas += 1
                numero_fila += 1
                continue

            # Normalización de unidad
            unidad_norm = normalizar_unidad(unidad_cruda)

            # Normalización de fecha y cálculo de antigüedad
            fecha_iso, antiguedad_meses, fecha_ok, motivo_fecha = normalizar_fecha(fecha_cruda)
            desactualizado = 1 if antiguedad_meses > 6 else 0
            if not fecha_ok:
                # Si la fecha no es válida en el catálogo, se registra la advertencia o fecha nula pero se conserva si tiene precio válido
                fecha_iso = None

            # Inserción de fila válida
            conn.execute(
                """INSERT INTO catalogo (
                       fuente_id, sku, descripcion, categoria, unidad, precio_unitario, 
                       moneda, fecha_precio, desactualizado, antiguedad_meses, notas, archivo_origen
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fuente_id, sku_crudo, desc_cruda, cat_cruda, unidad_norm, precio_val,
                    "MXN", fecha_iso, desactualizado, antiguedad_meses, notas_crudas, nombre_archivo
                )
            )
            guardadas += 1
            numero_fila += 1

    finally:
        if debe_cerrar:
            f.close()

    return {
        "leidas": leidas,
        "guardadas": guardadas,
        "rechazadas": rechazadas,
        "omitidas": omitidas
    }
