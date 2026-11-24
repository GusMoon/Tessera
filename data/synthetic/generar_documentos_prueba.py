"""Documentos ficticios para probar el agente de Tessera a mano (no son parte de los hitos).

Genera en `data/pruebas_agente/`:
  - 4 solicitudes de clientes en formatos distintos (PDF, Excel, texto de WhatsApp, CSV) para adjuntar en el chat.
  - 1 lista de precios de un proveedor ficticio (CSV con 2 filas defectuosas) para probar «Fuentes» y los rechazos.
  - 1 política comercial interna (PDF) para probar permisos: se sube con permiso «Administración».

Todo es sintético: clientes, proveedor y cifras son inventados. Los artículos de las solicitudes salen del catálogo
sintético, así que el agente puede cotizarlos. Determinista (sin azar): correrlo dos veces da los mismos archivos.

Uso:  python data/synthetic/generar_documentos_prueba.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SALIDA = Path(__file__).resolve().parents[1] / "pruebas_agente"
ESTILOS = getSampleStyleSheet()
CUERPO = ParagraphStyle("cuerpo", parent=ESTILOS["BodyText"], fontSize=10.5, leading=15)


def _pdf(ruta: Path, titulo: str, bloques: list) -> None:
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, title=titulo, author="Datos sintéticos de Tessera",
                            leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    doc.build(bloques)


def _tabla(filas: list[list[str]], anchos: list[float]) -> Table:
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF2")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 1), (0, -1), "CENTER"),
    ]))
    return t


# --------------------------------------------------------------------------- solicitudes de clientes
def solicitud_hotel() -> None:
    """Solicitud formal en PDF (como la mandaría el área de compras de un hotel)."""
    h = ESTILOS["Heading2"]
    _pdf(SALIDA / "solicitud_01_hotel_costa_dorada.pdf", "Solicitud de cotización · Hotel Costa Dorada", [
        Paragraph("HOTEL COSTA DORADA (ficticio)", ESTILOS["Title"]),
        Paragraph("Departamento de Compras · Progreso, Yucatán · 18/11/2026", CUERPO),
        Spacer(1, 10),
        Paragraph("Solicitud de cotización · Remodelación del área de servicios", h),
        Paragraph("Estimado proveedor: para la remodelación del cuarto de máquinas y la nueva canalización del ala norte "
                  "necesitamos cotización de los materiales listados abajo, con instalación incluida y entrega "
                  "(flete) en la obra, en Progreso. Favor de indicar el precio por escenario y la vigencia.", CUERPO),
        Spacer(1, 8),
        _tabla([["Partida", "Descripción", "Cantidad"],
                ["1", "Gabinete metálico NEMA 4X intemperie 40x30x20", "12 piezas"],
                ["2", "Cable THW calibre 12 negro", "30 rollos"],
                ["3", "Tubo conduit pared delgada 3/4", "60 tramos"],
                ["4", "Coples conduit pared delgada 3/4", "120 piezas"]], [50, 330, 100]),
        Spacer(1, 10),
        Paragraph("Condiciones: instalación incluida de gabinetes y canalización; flete a Progreso; pago a 30 días.", CUERPO),
        Paragraph("Atentamente, Lic. Roberto Valdez (personaje ficticio) · compras@costadorada.example", CUERPO),
    ])


def solicitud_constructora() -> None:
    """Lista de materiales en Excel (como la arma un residente de obra)."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Pedido"
    hoja.append(["Constructora Peninsular (ficticia) · Pedido de materiales eléctricos · Fracc. Los Almendros"])
    hoja.append([])
    hoja.append(["Partida", "Concepto", "Cantidad", "Observaciones"])
    for celda in hoja[3]:
        celda.font = Font(bold=True)
        celda.fill = PatternFill("solid", fgColor="E8EEF2")
    filas = [
        (1, "Interruptores termomagnéticos 1P 20A", 24, "Para tableros de planta baja"),
        (2, "Interruptores termomagnéticos 1P 30A", 6, ""),
        (3, "Centros de carga 4 polos bifásico", 3, "Uno por departamento tipo"),
        (4, "Contactos dúplex aterrizados", 40, ""),
        (5, "Apagadores sencillos", 30, ""),
        (6, "Placas con chasis 3 módulos", 35, "Color marfil"),
    ]
    for f in filas:
        hoja.append(f)
    hoja.append([])
    hoja.append(["Entrega en Mérida. Cliente: Constructora Peninsular."])
    for col, ancho in zip("ABCD", (9, 44, 11, 34)):
        hoja.column_dimensions[col].width = ancho
    libro.save(SALIDA / "solicitud_02_constructora_peninsular.xlsx")


def solicitud_whatsapp() -> None:
    """Mensaje informal, como llegaría por chat."""
    (SALIDA / "solicitud_03_taller_los_pinos.txt").write_text(
        "[18/11/2026 09:12] Don Chuy (Taller Los Pinos): Buen día, me ayudas con una cotización\n"
        "[18/11/2026 09:12] Don Chuy (Taller Los Pinos): ocupo 3 reflectores LED 50W intemperie\n"
        "[18/11/2026 09:13] Don Chuy (Taller Los Pinos): y 10 luminarias LED gabinete 2x18W 1.20m\n"
        "[18/11/2026 09:13] Don Chuy (Taller Los Pinos): me las llevan a Umán, con flete\n"
        "[18/11/2026 09:14] Don Chuy (Taller Los Pinos): para esta semana si se puede 🙏\n",
        encoding="utf-8")


def solicitud_csv() -> None:
    """Lista exportada de una hoja de cálculo, con otro orden de columnas y unidades."""
    (SALIDA / "solicitud_04_obra_progreso.csv").write_text(
        "Obra,Concepto,Cantidad,Unidad\n"
        "Obra Progreso,Varillas de tierra Copperweld 5/8 con conector,8,pza\n"
        "Obra Progreso,Cable THW calibre 8 verde,10,rollo\n"
        "Obra Progreso,Tubo conduit pared gruesa 1 pulg,40,tramo\n"
        "Obra Progreso,Instalación de canalización,,\n"
        "Obra Progreso,Flete a Progreso (2 viajes),,\n", encoding="utf-8")


# --------------------------------------------------------------------------- fuentes de prueba
def lista_proveedor() -> None:
    """Catálogo de un proveedor ficticio, mismo formato que catalogo_materiales.csv, con 2 filas defectuosas."""
    (SALIDA / "fuente_proveedor_ferreteria_maya.csv").write_text(
        "SKU,Descripcion,Categoria,Unidad,Precio_Unitario,Moneda,Fecha_Precio,Notas\n"
        "FMY-REG-100,Registro eléctrico de concreto 40x40x40 cm con tapa,Registros,pza,\"$1,180.00 MXN\",MXN,12/11/2026,Proveedor Ferretería Maya (ficticio)\n"
        "FMY-CAB-14R,Cable de cobre THHW calibre 14 AWG rojo (rollo 100m),Conductores,rollo,\"$760.00\",MXN,10/11/2026,\n"
        "FMY-TUB-FLX,Tubo flexible liquidtight 1 pulg (rollo 15m),Canalización,rollo,\"$890.00 MXN\",MXN,10/11/2026,\n"
        "FMY-MUF-100,Mufa de 1 pulg para acometida con base,Acometidas,pza,215,MXN,09/11/2026,\n"
        "FMY-INT-115,Interruptor de seguridad 2P 30A uso rudo,Protecciones,pza,\"$640.00 MXN\",MXN,09/11/2026,\n"
        "FMY-CIN-ALU,Cinta de aluminio para ductos 48mm x 50m,Cintas,pza,$95.00 MXN,MXN,08/11/2026,\n"
        ",Material sin código de parte,Varios,pza,150,MXN,08/11/2026,Fila defectuosa: no trae SKU\n"
        "FMY-CAB-NEG,Cable con precio negativo,Conductores,m,-90,MXN,08/11/2026,Fila defectuosa: precio negativo\n",
        encoding="utf-8")


def politica_interna() -> None:
    """Documento que un Vendedor no debe poder usar: se sube con permiso «Administración»."""
    h = ESTILOS["Heading2"]
    _pdf(SALIDA / "fuente_politica_comercial_interna.pdf", "Política comercial interna (ficticia)", [
        Paragraph("Política comercial interna · SOLO ADMINISTRACIÓN", ESTILOS["Title"]),
        Paragraph("Código: POL-COM-001 | Fabricante: Documento interno de Tessera (ficticio) | Vigencia: 01/11/2026", CUERPO),
        Spacer(1, 8),
        Paragraph("Descuentos autorizados", h),
        Paragraph("Hasta 3% sin autorización. De 3% a 8% requiere aprobación del Responsable comercial. Más de 8% "
                  "requiere aprobación de Administración. Ningún descuento puede dejar el margen por debajo de 12%.", CUERPO),
        Paragraph("Margen mínimo por línea de producto", h),
        Paragraph("Gabinetes y tableros: 15%. Conductores: 10%. Canalización: 14%. Servicios de instalación: 20%.", CUERPO),
        Paragraph("Cliente de crédito", h),
        Paragraph("Límite de crédito para clientes nuevos: $150,000.00 MXN a 15 días. Constructora Peninsular tiene "
                  "autorizado un límite de $400,000.00 MXN a 30 días (dato ficticio de prueba).", CUERPO),
    ])


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for f in (solicitud_hotel, solicitud_constructora, solicitud_whatsapp, solicitud_csv, lista_proveedor, politica_interna):
        f()
    for a in sorted(SALIDA.iterdir()):
        print(f"{a.name}  ({a.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
