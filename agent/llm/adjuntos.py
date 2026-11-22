"""Lectura de archivos para dárselos como contexto a un LLM (pruebas por terminal).

- Texto, CSV, Excel y PDF se convierten a texto y se anteponen a la pregunta, rotulados con el
  nombre del archivo para que el modelo pueda citarlo como fuente (regla 2 de CLAUDE.md).
- Las imágenes se envían como ``image_url`` con datos en base64 (formato chat de OpenAI);
  solo funcionan con modelos que aceptan imágenes.

Este módulo NO escribe en la base de datos: es distinto de ``ingest/``, que valida y guarda.
"""

from __future__ import annotations

import base64
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXT_TEXTO = {".txt", ".md", ".json", ".log", ".xml", ".yaml", ".yml"}
EXT_CSV = {".csv", ".tsv"}
EXT_EXCEL = {".xlsx", ".xlsm"}
EXT_IMAGEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}

MAX_CARACTERES = 12_000  # por archivo; ~4,000 tokens con la heurística de agent/llm/tokens.py
MAX_BYTES_IMAGEN = 5 * 1024 * 1024
MAX_BYTES_ARCHIVO = 20 * 1024 * 1024


class ErrorAdjunto(Exception):
    """El archivo no se pudo leer; el mensaje es legible para el usuario."""


@dataclass(frozen=True)
class Adjunto:
    nombre: str
    tipo: str  # "texto" | "imagen"
    texto: str = ""  # contenido extraído (tipo "texto")
    data_url: str = ""  # data:image/...;base64,... (tipo "imagen")
    detalle: str = ""  # p. ej. "3 páginas", "2 hojas"
    caracteres_originales: int = 0
    truncado: bool = False

    @property
    def resumen(self) -> str:
        if self.tipo == "imagen":
            return f"{self.nombre} (imagen, {self.detalle})"
        extra = f", se recortó de {self.caracteres_originales:,} a {len(self.texto):,} caracteres" if self.truncado else ""
        return f"{self.nombre} ({self.detalle or 'texto'}, {len(self.texto):,} caracteres{extra})"


# --------------------------------------------------------------------------- lectura
def leer_adjunto(ruta: str | Path, max_caracteres: int = MAX_CARACTERES) -> Adjunto:
    p = Path(str(ruta).strip().strip('"').strip("'")).expanduser()
    if not p.is_file():
        raise ErrorAdjunto(f"No existe el archivo: {p}")
    ext = p.suffix.lower()
    tamano = p.stat().st_size

    if ext in EXT_IMAGEN:
        if tamano > MAX_BYTES_IMAGEN:
            raise ErrorAdjunto(f"La imagen pesa {tamano / 1_048_576:.1f} MB; el máximo es {MAX_BYTES_IMAGEN // 1_048_576} MB.")
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return Adjunto(p.name, "imagen", data_url=f"data:{EXT_IMAGEN[ext]};base64,{b64}", detalle=f"{tamano / 1024:.0f} KB")

    if tamano > MAX_BYTES_ARCHIVO:
        raise ErrorAdjunto(f"El archivo pesa {tamano / 1_048_576:.1f} MB; el máximo es {MAX_BYTES_ARCHIVO // 1_048_576} MB.")
    if ext in EXT_TEXTO:
        texto, detalle = _decodificar(p.read_bytes()), "texto"
    elif ext in EXT_CSV:
        texto, detalle = _leer_csv(p, "\t" if ext == ".tsv" else None)
    elif ext in EXT_EXCEL:
        texto, detalle = _leer_excel(p)
    elif ext == ".pdf":
        texto, detalle = _leer_pdf(p)
    else:
        validos = sorted(EXT_TEXTO | EXT_CSV | EXT_EXCEL | {".pdf"} | set(EXT_IMAGEN))
        raise ErrorAdjunto(f"Formato no soportado ({ext or 'sin extensión'}). Formatos: {', '.join(validos)}.")

    texto = texto.strip()
    if not texto:
        raise ErrorAdjunto(f"{p.name} no contiene texto legible.")
    original = len(texto)
    truncado = max_caracteres > 0 and original > max_caracteres
    if truncado:
        texto = texto[:max_caracteres] + "\n[... contenido recortado ...]"
    return Adjunto(p.name, "texto", texto=texto, detalle=detalle, caracteres_originales=original, truncado=truncado)


def _decodificar(datos: bytes) -> str:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1", errors="replace")


def _leer_csv(p: Path, delimitador: str | None) -> tuple[str, str]:
    texto = _decodificar(p.read_bytes())
    if delimitador is None:
        try:
            delimitador = csv.Sniffer().sniff(texto[:4096], delimiters=",;|\t").delimiter
        except csv.Error:
            delimitador = ","
    filas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    return "\n".join(" | ".join(c.strip() for c in fila) for fila in filas), f"CSV, {len(filas)} filas"


def _leer_excel(p: Path) -> tuple[str, str]:
    from openpyxl import load_workbook  # import diferido: solo se necesita para Excel

    try:
        libro = load_workbook(p, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl lanza tipos variados con archivos corruptos
        raise ErrorAdjunto(f"No se pudo abrir el Excel: {exc}") from None
    try:
        bloques, filas_total = [], 0
        for hoja in libro.worksheets:
            filas = []
            for fila in hoja.iter_rows(values_only=True):
                if any(c is not None and str(c).strip() for c in fila):
                    filas.append(" | ".join("" if c is None else str(c).strip() for c in fila))
            filas_total += len(filas)
            bloques.append(f"## Hoja: {hoja.title}\n" + "\n".join(filas))
        return "\n\n".join(bloques), f"{len(libro.worksheets)} hojas, {filas_total} filas"
    finally:
        libro.close()


def _leer_pdf(p: Path) -> tuple[str, str]:
    from pypdf import PdfReader

    try:
        lector = PdfReader(str(p))
        paginas = [(pag.extract_text() or "").strip() for pag in lector.pages]
    except Exception as exc:
        raise ErrorAdjunto(f"No se pudo leer el PDF: {exc}") from None
    if not any(paginas):
        raise ErrorAdjunto(
            f"{p.name} no tiene texto extraíble (posiblemente es un escaneo). "
            "Conviértelo a imagen (PNG/JPG) y adjúntalo con un modelo que acepte imágenes."
        )
    return "\n\n".join(paginas), f"PDF, {len(paginas)} páginas"


# --------------------------------------------------------------------------- mensaje
def construir_contenido(pregunta: str, adjuntos: list[Adjunto]) -> str | list[dict[str, Any]]:
    """Arma el ``content`` del mensaje de usuario: ``str`` si no hay imágenes; lista de partes si las hay."""
    bloques = [f"[ARCHIVO: {a.nombre}]\n{a.texto}\n[FIN DE {a.nombre}]" for a in adjuntos if a.tipo == "texto"]
    texto = "\n\n".join([*bloques, pregunta]) if bloques else pregunta
    imagenes = [a for a in adjuntos if a.tipo == "imagen"]
    if not imagenes:
        return texto
    nombres = ", ".join(a.nombre for a in imagenes)
    partes: list[dict[str, Any]] = [{"type": "text", "text": f"{texto}\n\n(Imágenes adjuntas: {nombres})"}]
    partes += [{"type": "image_url", "image_url": {"url": a.data_url}} for a in imagenes]
    return partes
