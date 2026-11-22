"""Lector y validador de historial de cotizaciones en formato XLSX para Tessera."""

import io
import sqlite3
from pathlib import Path
from typing import Union, BinaryIO

import openpyxl

from ingest.validador import normalizar_fecha, normalizar_moneda, normalizar_cantidad, normalizar_unidad


def procesar_excel_cotizaciones(
    archivo_o_ruta: Union[str, Path, BinaryIO, bytes],
    fuente_id: int,
    nombre_archivo: str,
    conn: sqlite3.Connection
) -> dict:
    """
    Lee, valida y guarda las cotizaciones y partidas válidas del XLSX en SQLite.
    Detecta partidas duplicadas y precios > 6 meses (los marca, no los descarta).
    Registra rechazos legibles en la tabla 'rechazos'.
    Retorna métricas: {'leidas': int, 'guardadas': int, 'rechazadas': int, 'omitidas': int}
    """
    if isinstance(archivo_o_ruta, (str, Path)):
        wb = openpyxl.load_workbook(archivo_o_ruta, data_only=True)
    elif isinstance(archivo_o_ruta, bytes):
        wb = openpyxl.load_workbook(io.BytesIO(archivo_o_ruta), data_only=True)
    else:
        wb = openpyxl.load_workbook(archivo_o_ruta, data_only=True)

    ws = wb.active
    
    leidas = 0
    guardadas = 0
    rechazadas = 0
    omitidas = 0

    # Identificar encabezados en la primera fila
    headers = [cell.value for cell in ws[1]]
    header_indices = {}
    for idx, h in enumerate(headers):
        if h:
            header_indices[str(h).strip().lower()] = idx

    # Mapeo de columnas requeridas
    idx_folio = header_indices.get("folio", 0)
    idx_cliente = header_indices.get("cliente", 1)
    idx_fecha = header_indices.get("fecha", 2)
    idx_partida = header_indices.get("partida", 3)
    idx_concepto = header_indices.get("concepto", 4)
    idx_cantidad = header_indices.get("cantidad", 5)
    idx_unidad = header_indices.get("unidad", 6)
    idx_precio = header_indices.get("precio_unitario", 7)
    idx_subtotal = header_indices.get("subtotal", 8)
    idx_notas = header_indices.get("notas", 9)

    # Rastrear partidas para detección de duplicadas
    partidas_vistas = set()
    cotizaciones_creadas = {}

    # Iterar filas de datos a partir de la fila 2
    for row_idx in range(2, ws.max_row + 1):
        row = ws[row_idx]
        
        # Verificar si la fila está completamente vacía
        if all(cell.value is None or str(cell.value).strip() == "" for cell in row):
            continue

        leidas += 1

        val_folio = row[idx_folio].value if idx_folio < len(row) else None
        val_cliente = row[idx_cliente].value if idx_cliente < len(row) else None
        val_fecha = row[idx_fecha].value if idx_fecha < len(row) else None
        val_partida = row[idx_partida].value if idx_partida < len(row) else 1
        val_concepto = row[idx_concepto].value if idx_concepto < len(row) else None
        val_cantidad = row[idx_cantidad].value if idx_cantidad < len(row) else None
        val_unidad = row[idx_unidad].value if idx_unidad < len(row) else None
        val_precio = row[idx_precio].value if idx_precio < len(row) else None
        val_notas = row[idx_notas].value if idx_notas < len(row) else ""

        folio_str = str(val_folio).strip() if val_folio else "COT-SINFOLIO"
        cliente_str = str(val_cliente).strip() if val_cliente else "Cliente General"
        concepto_str = str(val_concepto).strip() if val_concepto is not None else ""

        # Validación 1: Concepto no puede estar vacío
        if not concepto_str:
            conn.execute(
                """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (fuente_id, nombre_archivo, row_idx, "Concepto", "", "Concepto o descripción faltante")
            )
            rechazadas += 1
            continue

        # Validación 2: Cantidad numérica y > 0
        cant_val, cant_ok, motivo_cant = normalizar_cantidad(val_cantidad)
        if not cant_ok:
            conn.execute(
                """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (fuente_id, nombre_archivo, row_idx, "Cantidad", str(val_cantidad if val_cantidad is not None else ""), motivo_cant)
            )
            rechazadas += 1
            continue

        # Validación 3: Precio unitario numérico y >= 0
        precio_val, precio_ok, motivo_precio = normalizar_moneda(val_precio)
        if not precio_ok:
            conn.execute(
                """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (fuente_id, nombre_archivo, row_idx, "Precio_Unitario", str(val_precio if val_precio is not None else ""), motivo_precio)
            )
            rechazadas += 1
            continue

        # Validación 4: Fecha válida
        fecha_iso, antiguedad_meses, fecha_ok, motivo_fecha = normalizar_fecha(val_fecha)
        if not fecha_ok:
            conn.execute(
                """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
                (fuente_id, nombre_archivo, row_idx, "Fecha", str(val_fecha if val_fecha is not None else ""), motivo_fecha)
            )
            rechazadas += 1
            continue

        # Detección de antigüedad > 6 meses (se marca, no se rechaza)
        desactualizado = 1 if antiguedad_meses > 6 else 0

        # Detección de duplicados (se marca duplicada=1, no se rechaza)
        clave_partida = (folio_str, concepto_str.lower())
        duplicada = 1 if clave_partida in partidas_vistas else 0
        partidas_vistas.add(clave_partida)

        # Normalizar unidad
        unidad_norm = normalizar_unidad(val_unidad)
        subtotal_val = round(cant_val * precio_val, 2)

        # Crear o recuperar cabecera de cotización histórica
        if folio_str not in cotizaciones_creadas:
            cur = conn.execute(
                """INSERT INTO cotizaciones_historicas (fuente_id, folio, cliente, fecha, desactualizado, archivo_origen)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (fuente_id, folio_str, cliente_str, fecha_iso, desactualizado, nombre_archivo)
            )
            cotizacion_id = cur.lastrowid
            cotizaciones_creadas[folio_str] = cotizacion_id
        else:
            cotizacion_id = cotizaciones_creadas[folio_str]

        # Inserción de la partida histórica válida
        try:
            partida_num = int(val_partida) if val_partida is not None else 1
        except (ValueError, TypeError):
            partida_num = 1

        conn.execute(
            """INSERT INTO partidas_historicas (
                   cotizacion_id, folio, partida_num, concepto, cantidad, unidad, 
                   precio_unitario, subtotal, duplicada, notas, archivo_origen
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cotizacion_id, folio_str, partida_num, concepto_str, cant_val, unidad_norm,
                precio_val, subtotal_val, duplicada, str(val_notas or ""), nombre_archivo
            )
        )
        guardadas += 1

    wb.close()

    return {
        "leidas": leidas,
        "guardadas": guardadas,
        "rechazadas": rechazadas,
        "omitidas": omitidas
    }
