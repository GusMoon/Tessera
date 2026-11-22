"""Servicio orquestador de ingesta de datos para Tessera."""

import hashlib
import sqlite3
from pathlib import Path
from typing import Union, BinaryIO, Optional

from db.database import get_connection
from ingest.lector_csv import procesar_csv_catalogo
from ingest.lector_excel import procesar_excel_cotizaciones
from ingest.lector_pdf import procesar_pdf_ficha


def procesar_archivo(
    archivo_o_ruta: Union[str, Path, BinaryIO, bytes],
    nombre_archivo: str,
    conn: Optional[sqlite3.Connection] = None
) -> dict:
    """
    Procesa un archivo (CSV, XLSX o PDF), valida sus filas, guarda las válidas
    en SQLite y registra los rechazos legibles en la tabla 'rechazos'.
    Actualiza la tabla 'fuentes' con el estado final y conteos exactos.
    """
    cerrar_conn = False
    if conn is None:
        conn = get_connection()
        cerrar_conn = True

    try:
        # Extraer extensión y calcular hash básico
        ext = Path(nombre_archivo).suffix.lower()
        if ext == ".csv":
            tipo_doc = "CSV"
        elif ext in (".xlsx", ".xls"):
            tipo_doc = "Excel"
        elif ext == ".pdf":
            tipo_doc = "PDF"
        else:
            tipo_doc = "Desconocido"

        if tipo_doc == "Desconocido":
            return {
                "nombre": nombre_archivo,
                "tipo": tipo_doc,
                "estado": "Error",
                "leidas": 0,
                "guardadas": 0,
                "rechazadas": 1,
                "omitidas": 0,
                "motivo": f"Formato no soportado ({ext}). Solo se admiten CSV, XLSX y PDF."
            }

        # Calcular hash y tamaño si son bytes o ruta
        tamano_bytes = 0
        hash_str = ""
        if isinstance(archivo_o_ruta, (str, Path)):
            p = Path(archivo_o_ruta)
            if p.exists():
                tamano_bytes = p.stat().st_size
                with open(p, "rb") as f_hash:
                    hash_str = hashlib.md5(f_hash.read()).hexdigest()
        elif isinstance(archivo_o_ruta, bytes):
            tamano_bytes = len(archivo_o_ruta)
            hash_str = hashlib.md5(archivo_o_ruta).hexdigest()

        # Registrar o actualizar fuente en SQLite
        cur = conn.execute("SELECT id FROM fuentes WHERE nombre = ?", (nombre_archivo,))
        row_fuente = cur.fetchone()
        
        if row_fuente:
            fuente_id = row_fuente["id"]
            # Limpiar datos previos si se está reprocesando
            conn.execute("DELETE FROM catalogo WHERE fuente_id = ?", (fuente_id,))
            conn.execute("DELETE FROM partidas_historicas WHERE cotizacion_id IN (SELECT id FROM cotizaciones_historicas WHERE fuente_id = ?)", (fuente_id,))
            conn.execute("DELETE FROM cotizaciones_historicas WHERE fuente_id = ?", (fuente_id,))
            conn.execute("DELETE FROM fichas_tecnicas WHERE fuente_id = ?", (fuente_id,))
            conn.execute("DELETE FROM rechazos WHERE fuente_id = ?", (fuente_id,))
            conn.execute(
                """UPDATE fuentes 
                   SET estado = 'Procesando', hash_archivo = ?, tamano_bytes = ?, fecha_carga = datetime('now', 'localtime')
                   WHERE id = ?""",
                (hash_str, tamano_bytes, fuente_id)
            )
        else:
            cur = conn.execute(
                """INSERT INTO fuentes (nombre, tipo, hash_archivo, tamano_bytes, estado, fecha_carga)
                   VALUES (?, ?, ?, ?, 'Procesando', datetime('now', 'localtime'))""",
                (nombre_archivo, tipo_doc, hash_str, tamano_bytes)
            )
            fuente_id = cur.lastrowid

        # Ejecutar lector según tipo
        if tipo_doc == "CSV":
            metricas = procesar_csv_catalogo(archivo_o_ruta, fuente_id, nombre_archivo, conn)
        elif tipo_doc == "Excel":
            metricas = procesar_excel_cotizaciones(archivo_o_ruta, fuente_id, nombre_archivo, conn)
        elif tipo_doc == "PDF":
            metricas = procesar_pdf_ficha(archivo_o_ruta, fuente_id, nombre_archivo, conn)

        # Estado final del archivo:
        # Si no hubo filas guardadas y todas fueron rechazadas, es 'Error'; de lo contrario 'Listo'.
        if metricas["guardadas"] == 0 and metricas["rechazadas"] > 0:
            estado_final = "Error"
            motivo_final = "El archivo fue rechazado completamente por inconsistencias."
        else:
            estado_final = "Listo"
            motivo_final = None

        conn.execute(
            """UPDATE fuentes 
               SET estado = ?, filas_leidas = ?, filas_guardadas = ?, 
                   filas_rechazadas = ?, filas_omitidas = ?, motivo = ?
               WHERE id = ?""",
            (
                estado_final, metricas["leidas"], metricas["guardadas"],
                metricas["rechazadas"], metricas["omitidas"], motivo_final, fuente_id
            )
        )
        conn.commit()

        return {
            "fuente_id": fuente_id,
            "nombre": nombre_archivo,
            "tipo": tipo_doc,
            "estado": estado_final,
            "leidas": metricas["leidas"],
            "guardadas": metricas["guardadas"],
            "rechazadas": metricas["rechazadas"],
            "omitidas": metricas["omitidas"],
            "motivo": motivo_final
        }

    finally:
        if cerrar_conn:
            conn.close()
