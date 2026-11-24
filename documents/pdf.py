"""PDF de la cotización aprobada (ReportLab, licencia BSD).

Regla 3 de CLAUDE.md: nada sale sin aprobación humana. `generar_pdf` es la ÚNICA puerta de entrada y exige una fila
en `aprobaciones` y que la cotización esté en estado «Aprobada»; el dibujo (`_dibujar`) es privado. El PDF cita la
fuente de cada partida (regla 2) y marca los precios de más de 6 meses.
"""

from __future__ import annotations

import io
import sqlite3
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from agent.cotizaciones import ETIQUETAS, obtener
from agent.tools.calcular_cotizacion import TASA_IVA_PORCIENTO

EMPRESA = "Materiales del Sureste (empresa ficticia)"


class AprobacionRequerida(Exception):
    """No existe una aprobación registrada: no se genera el PDF (regla 3)."""


class IntegridadError(Exception):
    """El total recalculado no coincide con el que se aprobó: algo cambió después de aprobar."""


def _pesos(centavos: int) -> str:
    return f"${centavos / 100:,.2f}"


def _fecha(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def generar_pdf(conn: sqlite3.Connection, cotizacion_id: int) -> bytes:
    """Devuelve el PDF de una cotización aprobada. Lanza `AprobacionRequerida` si no hay aprobación registrada."""
    aprobacion = conn.execute(
        """SELECT a.escenario, a.aprobado_por, a.fecha, a.total_centavos, c.estado
           FROM aprobaciones a JOIN cotizaciones c ON c.id = a.cotizacion_id WHERE a.cotizacion_id = ?""",
        (cotizacion_id,),
    ).fetchone()
    if aprobacion is None or aprobacion["estado"] != "Aprobada":
        raise AprobacionRequerida("La cotización no tiene una aprobación registrada: no se puede generar el PDF.")
    cot = obtener(conn, cotizacion_id, aprobacion["aprobado_por"])
    escenario = cot["escenarios"][aprobacion["escenario"]]
    if escenario["totales"]["total_centavos"] != aprobacion["total_centavos"]:
        raise IntegridadError("El total actual no coincide con el aprobado; la cotización cambió después de aprobarse.")
    return _dibujar(cot, aprobacion["escenario"], escenario)


def _dibujar(cot: dict, escenario_id: str, esc: dict) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"Cotización {cot['folio']}", author="Tessera", subject=f"Cotización {cot['folio']} para {cot['cliente']}",
    )
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontSize=9, leading=12)
    chico = ParagraphStyle("chico", parent=normal, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444"))
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=18, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=estilos["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)

    t = esc["totales"]
    elementos = [
        Paragraph(f"Cotización {cot['folio']}", titulo),
        Paragraph(f"{EMPRESA} · Mérida, Yucatán", chico),
        Spacer(1, 8),
        Paragraph(f"<b>Cliente:</b> {cot['cliente']}", normal),
        Paragraph(f"<b>Fecha:</b> {_fecha(cot['fecha'])} &nbsp;&nbsp; <b>Escenario:</b> {ETIQUETAS[escenario_id]} &nbsp;&nbsp; "
                  f"<b>Elaborada por:</b> {cot['creada_por']}", normal),
        Paragraph(f"<b>Solicitud:</b> {cot['solicitud']}", normal),
        Paragraph("Partidas", h2),
    ]

    filas = [["Concepto", "Cant.", "Unidad", "P. unit. (MXN)", "Importe (MXN)", "Fuente"]]
    for p in esc["partidas"]:
        fuente = f"{p['fuente_ref']}<br/>{_fecha(p['fuente_fecha'])}"
        if p["precio_antiguo"]:
            fuente += f"<br/><b>(!) precio de {p['antiguedad_meses']} meses</b>"
        filas.append([
            Paragraph(p["concepto"], chico), str(p["cantidad"]), p["unidad"], _pesos(p["precio_unitario_centavos"]),
            _pesos(p["importe_centavos"]), Paragraph(fuente, chico),
        ])
    tabla = Table(filas, colWidths=[6.0 * cm, 1.3 * cm, 1.6 * cm, 2.4 * cm, 2.5 * cm, 3.6 * cm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("FONT", (1, 1), (-1, -1), "Helvetica", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E4DA")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
        ("ALIGN", (1, 0), (4, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos += [tabla, Spacer(1, 8)]

    totales = Table(
        [["Subtotal", _pesos(t["subtotal_centavos"])], [f"IVA ({TASA_IVA_PORCIENTO} %)", _pesos(t["iva_centavos"])],
         ["Total MXN", _pesos(t["total_centavos"])]],
        colWidths=[3.2 * cm, 3.4 * cm], hAlign="RIGHT",
    )
    totales.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("FONT", (0, 2), (-1, 2), "Helvetica-Bold", 11),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.black),
    ]))
    elementos.append(totales)

    if esc["notas"].strip():
        elementos += [Paragraph("Notas", h2), Paragraph(esc["notas"].replace("\n", "<br/>"), normal)]

    elementos.append(Paragraph("Fuentes citadas", h2))
    citadas = {p["fuente_ref"] for p in esc["partidas"]}
    for ref in sorted(citadas):
        f = cot["fuentes"].get(ref, {})
        origen = f.get("documento") or "fuente no disponible"
        elementos.append(Paragraph(f"<b>{ref}</b> · {origen} · dato del {_fecha(f.get('fecha'))}", chico))
    if cot["parecidas"]:
        elementos.append(Paragraph(
            "Cotizaciones históricas parecidas consultadas: " + ", ".join(h["folio"] for h in cot["parecidas"]) + ".", chico))

    elementos += [
        Spacer(1, 14),
        Paragraph(f"<b>Aprobada por {cot['aprobada_por']}</b> el {_fecha(cot['fecha_aprobacion'])}. "
                  "Los importes los calculó código determinista; ningún modelo de IA calculó cifras de este documento.", normal),
        Spacer(1, 6),
        Paragraph("Documento de prototipo con datos sintéticos; no tiene validez comercial.", chico),
    ]
    documento.build(elementos)
    return buffer.getvalue()
