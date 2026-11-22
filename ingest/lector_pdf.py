"""Lector y extractor de texto de fichas técnicas en PDF para Tessera usando pypdf."""

import io
import re
import sqlite3
from pathlib import Path
from typing import Union, BinaryIO

from pypdf import PdfReader


def procesar_pdf_ficha(
    archivo_o_ruta: Union[str, Path, BinaryIO, bytes],
    fuente_id: int,
    nombre_archivo: str,
    conn: sqlite3.Connection
) -> dict:
    """
    Extrae texto completo de una ficha técnica PDF con pypdf y lo guarda en 'fichas_tecnicas'.
    Registra error legible en 'rechazos' si el PDF está corrupto.
    Retorna métricas: {'leidas': 1, 'guardadas': int, 'rechazadas': int, 'omitidas': int}
    """
    leidas = 1
    guardadas = 0
    rechazadas = 0
    omitidas = 0

    try:
        if isinstance(archivo_o_ruta, (str, Path)):
            reader = PdfReader(str(archivo_o_ruta))
        elif isinstance(archivo_o_ruta, bytes):
            reader = PdfReader(io.BytesIO(archivo_o_ruta))
        else:
            reader = PdfReader(archivo_o_ruta)

        num_paginas = len(reader.pages)
        if num_paginas == 0:
            raise ValueError("El archivo PDF no contiene páginas")

        texto_completo = []
        for i, pagina in enumerate(reader.pages):
            texto_p = pagina.extract_text() or ""
            texto_completo.append(texto_p.strip())

        texto_unido = "\n\n--- PÁGINA ---\n\n".join(texto_completo).strip()
        if not texto_unido:
            raise ValueError("No se pudo extraer texto legible del PDF (posiblemente escaneado o vacío)")

        # Intentar extraer metadatos del texto
        codigo_match = re.search(r'C[oó]digo(?:\s+de\s+producto)?[:\s]+([A-Z0-9\-_]+)', texto_unido, re.IGNORECASE)
        codigo = codigo_match.group(1).strip() if codigo_match else None

        fabricante_match = re.search(r'Fabricante[:\s]+([^\n\r\|]+)', texto_unido, re.IGNORECASE)
        fabricante = fabricante_match.group(1).strip() if fabricante_match else None

        # Título a partir de la primera línea o nombre de archivo
        primeras_lineas = [l.strip() for l in texto_unido.split("\n") if l.strip()]
        titulo = primeras_lineas[0] if primeras_lineas else nombre_archivo
        if len(titulo) > 200:
            titulo = titulo[:197] + "..."

        conn.execute(
            """INSERT INTO fichas_tecnicas (
                   fuente_id, codigo, titulo, fabricante, contenido_texto, 
                   num_paginas, archivo_origen, fecha_carga
               ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
            (
                fuente_id, codigo, titulo, fabricante, texto_unido,
                num_paginas, nombre_archivo
            )
        )
        guardadas = 1

    except Exception as e:
        motivo = f"Error al leer PDF: {str(e)}"
        conn.execute(
            """INSERT INTO rechazos (fuente_id, archivo, fila_numero, campo, valor_crudo, motivo, fecha)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
            (fuente_id, nombre_archivo, 1, "Archivo_PDF", str(e), motivo)
        )
        rechazadas = 1

    return {
        "leidas": leidas,
        "guardadas": guardadas,
        "rechazadas": rechazadas,
        "omitidas": omitidas
    }
