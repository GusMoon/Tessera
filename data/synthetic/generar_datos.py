"""Generador de datos sintéticos para el proyecto Tessera (Hito 1).

Genera:
1. catalogo_materiales.csv (50 filas: 47 válidas, 3 defectuosas plantadas)
2. historial_cotizaciones.xlsx (120 filas: 115 válidas, 5 defectuosas plantadas)
3. 10 fichas técnicas en PDF (formato legible, extracción con pypdf)
4. tarifario_servicios.csv (15 servicios válidos: fletes por zona, instalación por pieza, opcionales premium)
5. manifiesto.json (conteo esperado, detalle de las 8 filas defectuosas y sus motivos)

Uso:
    python data/synthetic/generar_datos.py                    # regenera todo
    python data/synthetic/generar_datos.py --solo-tarifario   # solo el tarifario; actualiza el manifiesto sin tocar lo demás

Contexto: Suministro de materiales eléctricos y de construcción en Mérida, Yucatán.
Semilla fija (seed=42) para reproducibilidad total.
"""

import os
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Directorio de salida
OUTPUT_DIR = Path(__file__).resolve().parent
FICHAS_DIR = OUTPUT_DIR / "fichas_tecnicas"

# Semilla fija
SEMILLA = 42
random.seed(SEMILLA)
Faker.seed(SEMILLA)
fake = Faker('es_MX')

# Fecha base de referencia para el cálculo de antigüedad (Noviembre 2026)
FECHA_REFERENCIA = datetime(2026, 11, 21)

# Catálogo base de materiales en Mérida, Yucatán
MATERIALES_BASE = [
    ("GAB-303015", "Gabinete metálico sobreponer NEMA 1 30x30x15 cm cal 16", "Gabinetes", "pza", 850.00),
    ("GAB-403020", "Gabinete metálico NEMA 4X intemperie 40x30x20 cm cal 14", "Gabinetes", "pza", 1650.00),
    ("GAB-504020", "Gabinete autosoportado NEMA 12 50x40x20 cm", "Gabinetes", "PZA", 2420.00),
    ("CAB-THW-12N", "Cable de cobre THW-LS Calibre 12 AWG Negro (rollo 100m)", "Conductores", "rollo", 1250.00),
    ("CAB-THW-12R", "Cable de cobre THW-LS Calibre 12 AWG Rojo (rollo 100m)", "Conductores", "rollo", 1250.00),
    ("CAB-THW-10B", "Cable de cobre THW-LS Calibre 10 AWG Blanco (rollo 100m)", "Conductores", "ROLLO", 1890.00),
    ("CAB-THW-08V", "Cable de cobre THW-LS Calibre 8 AWG Verde (rollo 100m)", "Conductores", "rollo", 2980.00),
    ("TUB-CND-075", "Tubo conduit galvanizado pared delgada 3/4 pulg x 3m", "Canalización", "tramo", 145.00),
    ("TUB-CND-100", "Tubo conduit galvanizado pared delgada 1 pulg x 3m", "Canalización", "tramo", 215.00),
    ("TUB-CND-G075", "Tubo conduit galvanizado pared gruesa 3/4 pulg x 3m", "Canalización", "tramo", 310.00),
    ("TUB-CND-G100", "Tubo conduit galvanizado pared gruesa 1 pulg x 3m", "Canalización", "TRAMO", 445.00),
    ("COP-CND-075", "Cople conduit pared delgada 3/4 pulg con tornillo", "Conexiones", "pz", 12.50),
    ("COP-CND-100", "Cople conduit pared delgada 1 pulg con tornillo", "Conexiones", "pza", 18.00),
    ("CON-CND-075", "Conector conduit pared delgada 3/4 pulg", "Conexiones", "pieza", 14.00),
    ("CON-CND-100", "Conector conduit pared delgada 1 pulg", "Conexiones", "pz", 21.00),
    ("ABR-UNA-075", "Abrazadera tipo uña para conduit 3/4 pulg galvanizada", "Fijación", "pza", 6.50),
    ("ABR-UNA-100", "Abrazadera tipo uña para conduit 1 pulg galvanizada", "Fijación", "Pieza", 9.00),
    ("CC-4P-BIF", "Centro de carga 4 polos Square D QOD4F bifásico empotrar", "Tableros", "pza", 480.00),
    ("CC-8P-TRI", "Centro de carga 8 polos Square D trifásico sobreponer", "Tableros", "PZA", 890.00),
    ("CC-12P-TRI", "Centro de carga 12 polos Square D trifásico zapatas principales", "Tableros", "pza", 1350.00),
    ("INT-TM-120", "Interruptor termomagnético 1P 20A Square D QO120", "Protección", "pza", 175.00),
    ("INT-TM-130", "Interruptor termomagnético 1P 30A Square D QO130", "Protección", "pz", 175.00),
    ("INT-TM-230", "Interruptor termomagnético 2P 30A Square D QO230", "Protección", "pza", 460.00),
    ("INT-TM-250", "Interruptor termomagnético 2P 50A Square D QO250", "Protección", "pza", 520.00),
    ("INT-TM-360", "Interruptor termomagnético 3P 60A Square D QO360", "Protección", "PZA", 980.00),
    ("CAJ-FS-075", "Caja registro FS galvanizada 1 elemento 3/4 pulg", "Cajas", "pza", 85.00),
    ("CAJ-FD-075", "Caja registro FD doble fondo galvanizada 3/4 pulg", "Cajas", "pieza", 125.00),
    ("CAJ-CH-4X4", "Caja cuadrada chalupa 4x4 pulg galvanizada cal 18", "Cajas", "pz", 28.00),
    ("TAP-CH-4X4", "Tapa ciega cuadrada 4x4 pulg galvanizada", "Cajas", "pza", 14.50),
    ("TUB-PVC-H050", "Tubo PVC hidráulico cédula 40 1/2 pulg x 6m", "Tubería Hidráulica", "tramo", 115.00),
    ("TUB-PVC-H075", "Tubo PVC hidráulico cédula 40 3/4 pulg x 6m", "Tubería Hidráulica", "tramo", 168.00),
    ("TUB-PVC-H100", "Tubo PVC hidráulico cédula 40 1 pulg x 6m", "Tubería Hidráulica", "TRAMO", 260.00),
    ("TUB-PVC-H200", "Tubo PVC hidráulico cédula 40 2 pulg x 6m", "Tubería Hidráulica", "tramo", 580.00),
    ("TUB-PVC-S100", "Tubo PVC sanitario 4 pulg (100mm) x 6m norma", "Tubería Sanitaria", "tramo", 495.00),
    ("TUB-PVC-S050", "Tubo PVC sanitario 2 pulg (50mm) x 6m norma", "Tubería Sanitaria", "tramo", 280.00),
    ("PEG-PVC-250", "Pegamento para PVC azul secado rápido bote 250ml", "Químicos", "pza", 89.00),
    ("LIM-PVC-250", "Limpiador primer para PVC bote 250ml", "Químicos", "pz", 75.00),
    ("CINT-AIS-3M", "Cinta de aislar vinílica 3M Scotch 1700 19mm x 18m", "Consumibles", "pza", 38.00),
    ("CINT-VUL-3M", "Cinta vulcanizable para empalmes alta tensión 3M 23", "Consumibles", "rollo", 185.00),
    ("VAR-COP-58", "Varilla de tierra Copperweld 5/8 pulg x 1.5m con conector", "Puesta a Tierra", "pza", 320.00),
    ("CON-VAR-58", "Conector mecánico para varilla de tierra 5/8 pulg bronce", "Puesta a Tierra", "pza", 45.00),
    ("LAM-LED-60", "Luminaria LED tipo gabinete sobreponer 2x18W 1.20m", "Iluminación", "pza", 340.00),
    ("LAM-REF-50", "Reflector LED intemperie 50W 6500K IP65 carcasa aluminio", "Iluminación", "PZA", 290.00),
    ("AP-ESC-SN", "Apagador sencillo 1 módulo Simon 25 marfil", "Placas", "pieza", 42.00),
    ("CON-DUP-SN", "Contacto dúplex aterrizado Simon 25 marfil", "Placas", "pza", 58.00),
    ("PLA-3MOD-SN", "Placa con chasis 3 módulos Simon 25 marfil", "Placas", "pz", 28.00),
    ("TAB-PST-05", "Taquete plástico con pija cabeza fijadora 1/4 pulg bolsa 100 pz", "Fijación", "bolsa", 65.00),
    ("TOR-AUT-01", "Tornillo autotornillable galvanizado 1 pulg bolsa 100 pz", "Fijación", "bolsa", 72.00),
    ("SEL-POL-280", "Sellador poliuretano gris cartucho 280ml para juntas", "Químicos", "pza", 135.00),
    ("CAN-EST-01", "Canaleta plástica blanca con adhesivo 20x10mm tramo 2m", "Canalización", "tramo", 35.00),
]

CLIENTES_MERIDA = [
    "Constructora Peninsular del Mayab S.A. de C.V.",
    "Desarrollos Residenciales Altabrisa",
    "Inmobiliaria y Edificaciones Montebello",
    "Instalaciones Eléctricas Industriales de Yucatán",
    "Grupo Constructor Kanasín y Conkal",
    "Obras y Urbanizaciones de Mérida S.A.",
    "Edificadora del Sureste peninsular",
    "Proyectos de Infraestructura Chuburná",
    "Constructora Maya Colonial S. de R.L.",
    "Suministros Civiles de la Costa de Progreso"
]


def formatear_moneda(valor: float, formato: int) -> str:
    """Devuelve moneda con suciedad de formato."""
    if formato == 0:
        return f"${valor:,.2f} MXN"
    elif formato == 1:
        return f"{valor:.2f}"
    elif formato == 2:
        return f"$ {valor:,.2f}"
    elif formato == 3:
        return f"{valor:.1f} MXN"
    else:
        return str(valor)


def formatear_fecha(dt: datetime, formato: int) -> str:
    """Devuelve fecha con suciedad de formato."""
    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    if formato == 0:
        return dt.strftime("%d/%m/%Y")
    elif formato == 1:
        return dt.strftime("%Y-%m-%d")
    elif formato == 2:
        return dt.strftime("%d-%m-%Y")
    elif formato == 3:
        return dt.strftime("%Y/%m/%d")
    else:
        return f"{dt.day} de {meses_es[dt.month - 1]} de {dt.year}"


def generar_catalogo_csv() -> tuple[list[dict], list[dict]]:
    """Genera 50 filas para catalogo_materiales.csv (47 válidas + 3 defectuosas plantadas)."""
    filas = []
    rechazos_esperados = []
    
    # 47 filas válidas a partir de MATERIALES_BASE (índices 0 a 46)
    for i in range(47):
        base = MATERIALES_BASE[i]
        # Variedad de antigüedad: 12 filas con más de 6 meses (precios de 2025 o antes)
        if i % 4 == 0:
            dias_atras = random.randint(200, 450)  # > 6 meses
        else:
            dias_atras = random.randint(10, 120)   # Recientes
        
        fecha_dt = FECHA_REFERENCIA - timedelta(days=dias_atras)
        fecha_str = formatear_fecha(fecha_dt, i % 5)
        precio_str = formatear_moneda(base[4], i % 5)
        
        filas.append({
            "SKU": base[0],
            "Descripcion": base[1],
            "Categoria": base[2],
            "Unidad": base[3],
            "Precio_Unitario": precio_str,
            "Moneda": "MXN" if i % 2 == 0 else "",
            "Fecha_Precio": fecha_str,
            "Notas": "Material estándar puesto en obra Mérida" if i % 3 == 0 else ""
        })
    
    # 3 Filas defectuosas plantadas en posiciones específicas:
    # 1. Defecto 1 (Posición 15 en el CSV final -> fila Excel/CSV número 16 con header)
    defecto_1 = {
        "SKU": "",  # SKU vacío
        "Descripcion": "Gabinete especial sin código de parte cal 14",
        "Categoria": "Gabinetes",
        "Unidad": "pza",
        "Precio_Unitario": "$1,980.00 MXN",
        "Moneda": "MXN",
        "Fecha_Precio": "15/04/2026",
        "Notas": "Defecto plantado: SKU faltante"
    }
    
    # 2. Defecto 2 (Posición 30 en el CSV final -> fila 32 con header)
    defecto_2 = {
        "SKU": "CAB-THW-NEG",
        "Descripcion": "Cable de cobre THW calibre 4 con precio negativo",
        "Categoria": "Conductores",
        "Unidad": "m",
        "Precio_Unitario": "-350.00",  # Precio negativo
        "Moneda": "MXN",
        "Fecha_Precio": "10/05/2026",
        "Notas": "Defecto plantado: Precio negativo"
    }
    
    # 3. Defecto 3 (Posición 48 en el CSV final -> fila 50 con header)
    defecto_3 = {
        "SKU": "TUB-ESP-999",
        "Descripcion": "Tubería especial cedula 80 sin cotización numérica",
        "Categoria": "Canalización",
        "Unidad": "tramo",
        "Precio_Unitario": "CONSULTAR",  # Precio no numérico
        "Moneda": "MXN",
        "Fecha_Precio": "01/06/2026",
        "Notas": "Defecto plantado: Precio no numérico"
    }
    
    # Insertar los defectos en posiciones fijas
    filas.insert(15, defecto_1)
    filas.insert(30, defecto_2)
    filas.append(defecto_3)
    
    # Registrar en rechazos esperados (fila 1-indexed considerando cabecera en fila 1)
    rechazos_esperados.append({
        "archivo": "catalogo_materiales.csv",
        "fila": 17,  # Posición 15 + 1 (por header) + 1 (1-indexed) = 17
        "campo": "SKU",
        "valor_crudo": "",
        "motivo": "SKU faltante o vacío"
    })
    rechazos_esperados.append({
        "archivo": "catalogo_materiales.csv",
        "fila": 32,  # Posición 30 + 1 (defecto previo) + 1 (header) = 32
        "campo": "Precio_Unitario",
        "valor_crudo": "-350.00",
        "motivo": "Precio unitario negativo"
    })
    rechazos_esperados.append({
        "archivo": "catalogo_materiales.csv",
        "fila": 51,  # Fila 50 (última) + 1 (header) = 51
        "campo": "Precio_Unitario",
        "valor_crudo": "CONSULTAR",
        "motivo": "Precio no numérico o vacío"
    })
    
    return filas, rechazos_esperados


def generar_historial_xlsx() -> tuple[list[dict], list[dict]]:
    """Genera 120 filas de partidas para historial_cotizaciones.xlsx (115 válidas + 5 defectuosas plantadas)."""
    filas = []
    rechazos_esperados = []
    
    folio_actual = 100
    partida_num = 1
    
    for i in range(115):
        if partida_num > 4 or i == 0:
            folio_actual += 1
            partida_num = 1
        
        folio = f"COT-MID-{folio_actual:04d}"
        cliente = CLIENTES_MERIDA[folio_actual % len(CLIENTES_MERIDA)]
        
        # Fecha de cotización: algunas viejas (> 6 meses) y otras recientes
        if folio_actual % 3 == 0:
            dias_atras = random.randint(210, 480)
        else:
            dias_atras = random.randint(15, 130)
        fecha_dt = FECHA_REFERENCIA - timedelta(days=dias_atras)
        fecha_str = formatear_fecha(fecha_dt, i % 5)
        
        mat = MATERIALES_BASE[i % len(MATERIALES_BASE)]
        cantidad = random.choice([2, 5, 10, 15, 20, 50, 100])
        precio_unitario = mat[4]
        
        # Suciedad controlada: partidas duplicadas a propósito (para probar detección de duplicados)
        if i in (23, 65):
            # Repetir exactamente el mismo folio y concepto de la fila previa
            folio = filas[-1]["Folio"]
            mat = [m for m in MATERIALES_BASE if m[1] == filas[-1]["Concepto"]][0]
            partida_num = 2
        
        subtotal = round(cantidad * precio_unitario, 2)
        
        filas.append({
            "Folio": folio,
            "Cliente": cliente,
            "Fecha": fecha_str,
            "Partida": partida_num,
            "Concepto": mat[1],
            "Cantidad": cantidad if i % 4 != 0 else str(cantidad),
            "Unidad": mat[3],
            "Precio_Unitario": formatear_moneda(precio_unitario, i % 4),
            "Subtotal": formatear_moneda(subtotal, i % 3),
            "Notas": "Condiciones comerciales estándar 30 días" if i % 2 == 0 else "Precio sujeto a volumen"
        })
        partida_num += 1

    # 5 Filas defectuosas plantadas:
    # Defecto 1: Cantidad no numérica
    d1 = {
        "Folio": "COT-MID-0180",
        "Cliente": "Constructora Peninsular del Mayab S.A. de C.V.",
        "Fecha": "12/03/2026",
        "Partida": 1,
        "Concepto": "Centro de carga 8 polos Square D",
        "Cantidad": "DOCE",  # Cantidad no numérica
        "Unidad": "pza",
        "Precio_Unitario": "$890.00 MXN",
        "Subtotal": "N/A",
        "Notas": "Defecto plantado: Cantidad texto"
    }
    
    # Defecto 2: Precio unitario negativo
    d2 = {
        "Folio": "COT-MID-0181",
        "Cliente": "Inmobiliaria y Edificaciones Montebello",
        "Fecha": "18/04/2026",
        "Partida": 1,
        "Concepto": "Tubo conduit galvanizado pared delgada 1 pulg",
        "Cantidad": 20,
        "Unidad": "tramo",
        "Precio_Unitario": "-215.00",  # Precio negativo
        "Subtotal": "-4300.00",
        "Notas": "Defecto plantado: Precio negativo"
    }
    
    # Defecto 3: Fecha inválida
    d3 = {
        "Folio": "COT-MID-0182",
        "Cliente": "Grupo Constructor Kanasín y Conkal",
        "Fecha": "32/13/2025",  # Fecha imposible
        "Partida": 1,
        "Concepto": "Cable de cobre THW-LS Calibre 12 AWG Negro",
        "Cantidad": 5,
        "Unidad": "rollo",
        "Precio_Unitario": "$1,250.00 MXN",
        "Subtotal": "$6,250.00 MXN",
        "Notas": "Defecto plantado: Fecha inválida"
    }
    
    # Defecto 4: Concepto o descripción faltante
    d4 = {
        "Folio": "COT-MID-0183",
        "Cliente": "Obras y Urbanizaciones de Mérida S.A.",
        "Fecha": "25/05/2026",
        "Partida": 1,
        "Concepto": "",  # Concepto vacío
        "Cantidad": 10,
        "Unidad": "pza",
        "Precio_Unitario": "$175.00 MXN",
        "Subtotal": "$1,750.00 MXN",
        "Notas": "Defecto plantado: Concepto vacío"
    }
    
    # Defecto 5: Cantidad menor o igual a cero o nula
    d5 = {
        "Folio": "COT-MID-0184",
        "Cliente": "Desarrollos Residenciales Altabrisa",
        "Fecha": "04/06/2026",
        "Partida": 1,
        "Concepto": "Varilla de tierra Copperweld 5/8 pulg",
        "Cantidad": 0,  # Cantidad 0
        "Unidad": "pza",
        "Precio_Unitario": "$320.00 MXN",
        "Subtotal": "0.00",
        "Notas": "Defecto plantado: Cantidad cero"
    }

    # Insertamos los 5 defectos en posiciones fijas:
    filas.insert(20, d1)  # Índice 20 -> fila 22
    filas.insert(45, d2)  # Índice 45 -> fila 48
    filas.insert(70, d3)  # Índice 70 -> fila 74
    filas.insert(95, d4)  # Índice 95 -> fila 100
    filas.append(d5)      # Última fila -> fila 121

    rechazos_esperados.append({
        "archivo": "historial_cotizaciones.xlsx",
        "fila": 22,
        "campo": "Cantidad",
        "valor_crudo": "DOCE",
        "motivo": "Cantidad no numérica"
    })
    rechazos_esperados.append({
        "archivo": "historial_cotizaciones.xlsx",
        "fila": 48,
        "campo": "Precio_Unitario",
        "valor_crudo": "-215.00",
        "motivo": "Precio unitario negativo"
    })
    rechazos_esperados.append({
        "archivo": "historial_cotizaciones.xlsx",
        "fila": 74,
        "campo": "Fecha",
        "valor_crudo": "32/13/2025",
        "motivo": "Fecha inválida"
    })
    rechazos_esperados.append({
        "archivo": "historial_cotizaciones.xlsx",
        "fila": 100,
        "campo": "Concepto",
        "valor_crudo": "",
        "motivo": "Concepto o descripción faltante"
    })
    rechazos_esperados.append({
        "archivo": "historial_cotizaciones.xlsx",
        "fila": 121,
        "campo": "Cantidad",
        "valor_crudo": "0",
        "motivo": "Cantidad menor o igual a cero o faltante"
    })

    return filas, rechazos_esperados


def guardar_xlsx(filas: list[dict], ruta_archivo: Path) -> None:
    """Guarda filas en un XLSX estilizado profesionalmente con openpyxl."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cotizaciones_Historicas"
    
    # Encabezados
    headers = list(filas[0].keys())
    ws.append(headers)
    
    # Estilos de cabecera
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
    
    # Filas de datos
    for fila in filas:
        ws.append([fila[h] for h in headers])
        
    # Autoajustar ancho de columnas
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    wb.save(ruta_archivo)


def generar_fichas_pdf() -> list[str]:
    """Genera 10 fichas técnicas en PDF en FICHAS_DIR con ReportLab."""
    FICHAS_DIR.mkdir(parents=True, exist_ok=True)
    fichas_generadas = []
    
    fichas_datos = [
        {
            "archivo": "ficha_01_gabinete_nema4x.pdf",
            "codigo": "GAB-NEMA4X-01",
            "titulo": "Ficha Técnica: Gabinete Metálico NEMA 4X Intemperie 40x30x20 cm",
            "fabricante": "Gabinetes y Envolventes del Sureste S.A. de C.V. (Mérida)",
            "descripcion": "Gabinete fabricado en lámina de acero rolada en frío calibre 14 con recubrimiento de pintura poliéster en polvo electrostática color gris RAL 7035. Diseñado para ambientes húmedos y salinos característicos de la península de Yucatán.",
            "especificaciones": [
                ("Dimensiones exteriores", "400 x 300 x 200 mm"),
                ("Grado de protección", "NEMA 4X / IP66"),
                ("Calibre lámina cuerpo", "Calibre 14 (1.9 mm)"),
                ("Placa de montaje", "Lámina galvanizada calibre 12"),
                ("Cierre", "Chapa de seguridad tipo cuarto de vuelta con llave"),
                ("Hermeticidad", "Empaque continuo de poliuretano espumado en puerta"),
                ("Norma aplicable", "NMX-J-235/1-ANCE / NOM-001-SEDE-2012")
            ]
        },
        {
            "archivo": "ficha_02_cable_thw_12.pdf",
            "codigo": "CAB-THW-12AWG",
            "titulo": "Ficha Técnica: Conductor Eléctrico Cobre THW-LS / THHW-LS 12 AWG",
            "fabricante": "Conductores Peninsulares S.A. de C.V.",
            "descripcion": "Conductor de cobre suave de 99.9% de pureza con aislamiento termoplástico a base de policloruro de vinilo (PVC) antiflama, con emisión reducida de humos densos y gases ácidos (LS).",
            "especificaciones": [
                ("Calibre conductor", "12 AWG (3.31 mm²)"),
                ("Voltaje nominal", "600 V"),
                ("Temperatura máxima seco", "90 °C"),
                ("Temperatura máxima mojado", "75 °C"),
                ("Capacidad de corriente en tubo", "20 A (a 30 °C ambiente)"),
                ("Presentación", "Rollo de 100 metros"),
                ("Norma oficial", "NOM-063-SCFI / NMX-J-010-ANCE")
            ]
        },
        {
            "archivo": "ficha_03_tubo_conduit_pg.pdf",
            "codigo": "TUB-CND-PG01",
            "titulo": "Ficha Técnica: Tubo Conduit de Acero Galvanizado Pared Gruesa 1 pulgada",
            "fabricante": "Tubos y Perfiles de Yucatán S.A.",
            "descripcion": "Tubería conduit de acero al carbón galvanizado por inmersión en caliente (interior y exterior) para instalaciones eléctricas industriales y comerciales clasificadas.",
            "especificaciones": [
                ("Diámetro nominal", "1 pulgada (25.4 mm)"),
                ("Longitud estándar", "3.00 metros con cople roscado"),
                ("Tipo de unión", "Roscado NPT cónico en ambos extremos"),
                ("Espesor de pared", "3.20 mm nominal"),
                ("Acabado", "Galvanizado electrolítico e inmersión térmica"),
                ("Resistencia mecánica", "Alta resistencia al aplastamiento e impacto"),
                ("Norma oficial", "NOM-001-SEDE-2012 / NMX-J-534-ANCE")
            ]
        },
        {
            "archivo": "ficha_04_centro_carga_bifasico.pdf",
            "codigo": "TAB-CC-BIF-04",
            "titulo": "Ficha Técnica: Centro de Carga Residencial 4 Circuitos Bifásico",
            "fabricante": "Sistemas de Distribución Eléctrica de Mérida",
            "descripcion": "Gabinete de centro de carga para empotrar o sobreponer, compatible con interruptores enchufables tipo QO. Adecuado para instalaciones domésticas bifásicas a 120/240 VCA.",
            "especificaciones": [
                ("Número de circuitos", "4 espacios para polos simples o 2 dobles"),
                ("Tensión de operación", "120 / 240 VCA, 1 fase 3 hilos"),
                ("Corriente nominal barra", "100 Amperes"),
                ("Material de barras", "Cobre estañado de alta conductividad"),
                ("Gabinete", "Lámina rolada en frío con acabado horneado gris"),
                ("Tipo de montaje", "Empotrar en muro de block / sobreponer"),
                ("Norma oficial", "NOM-003-SCFI / NMX-J-118/1-ANCE")
            ]
        },
        {
            "archivo": "ficha_05_interruptor_termomagnetico.pdf",
            "codigo": "INT-TM-1P20",
            "titulo": "Ficha Técnica: Interruptor Termomagnético Monopolar 1x20A Enchufable",
            "fabricante": "Dispositivos de Protección Peninsular",
            "descripcion": "Interruptor automático miniatura termomagnético de 1 polo, diseñado para protección contra sobrecargas y cortocircuitos en alimentadores y circuitos derivados de alumbrado y contactos.",
            "especificaciones": [
                ("Corriente nominal", "20 Amperes"),
                ("Número de polos", "1 polo"),
                ("Capacidad interruptiva", "10,000 Amperes (10 kA a 120 VCA)"),
                ("Curva de disparo", "Tiempo inverso / magnético instantáneo"),
                ("Mecanismo de montaje", "Enchufable (Plug-on tipo QO)"),
                ("Indicador visual", "Ventana Visi-Trip color naranja en disparo"),
                ("Norma oficial", "NOM-003-SCFI / NMX-J-266-ANCE")
            ]
        },
        {
            "archivo": "ficha_06_tubo_pvc_hidraulico.pdf",
            "codigo": "TUB-PVC-H-2IN",
            "titulo": "Ficha Técnica: Tubería PVC Hidráulica Cédula 40 Cementar 2 pulgadas",
            "fabricante": "Plásticos Industriales del Sureste (Umán, Yucatán)",
            "descripcion": "Tubería de policloruro de vinilo rígido sin plastificante (PVC-U) para conducción de agua a presión potable en sistemas de riego, piscinas e instalaciones hidráulicas comerciales.",
            "especificaciones": [
                ("Diámetro nominal", "2 pulgadas (60.3 mm exterior)"),
                ("Cédula / Presión", "Cédula 40 (280 PSI a 23 °C)"),
                ("Longitud", "6.00 metros por tramo"),
                ("Tipo de unión", "Espiga y campana para unión cementada"),
                ("Color", "Blanco brillante virgen"),
                ("Resistencia UV", "Aditivo estabilizador para exposición solar"),
                ("Norma aplicable", "NOM-001-CONAGUA / NMX-E-145/1-CNCP")
            ]
        },
        {
            "archivo": "ficha_07_varilla_copperweld.pdf",
            "codigo": "PAT-VAR-58",
            "titulo": "Ficha Técnica: Electrodo de Puesta a Tierra Copperweld 5/8 pulgada x 1.5m",
            "fabricante": "Puestas a Tierra Mayab",
            "descripcion": "Varilla con núcleo de acero de alta resistencia mecánica y recubrimiento exterior de cobre electrolítico de 0.254 mm (10 milésimas de pulgada) aplicado por electrólisis molecular.",
            "especificaciones": [
                ("Diámetro exterior", "5/8 pulgada (15.8 mm)"),
                ("Longitud total", "1.50 metros con punta cónica de hincado"),
                ("Espesor de capa de cobre", "Mínimo 254 micrones homogéneo"),
                ("Resistencia a la tracción", "Mínimo 600 N/mm²"),
                ("Accesorios incluidos", "Conector mecánico de bronce fundido"),
                ("Vida útil estimada", "Más de 30 años en suelos calcáreos de Yucatán"),
                ("Norma oficial", "NOM-001-SEDE-2012 / NMX-J-549-ANCE")
            ]
        },
        {
            "archivo": "ficha_08_luminaria_led_industrial.pdf",
            "codigo": "ILU-LUM-2X18W",
            "titulo": "Ficha Técnica: Luminaria LED Industrial Hermética 2x18W 1.20m",
            "fabricante": "Luminarias Ecológicas del Sureste",
            "descripcion": "Luminaria a prueba de vapor y polvo (Vapor Tight) fabricada con cuerpo de policarbonato reforzado y difusor opalino anti-deslumbramiento. Equipada con 2 tubos LED T8 de alta eficiencia.",
            "especificaciones": [
                ("Potencia total", "36 Watts (2 x 18W)"),
                ("Flujo luminoso", "3,600 lúmenes reales"),
                ("Temperatura de color", "6,500 Kelvin (Luz de día blanca)"),
                ("Eficacia lumínica", "100 lm/Watt"),
                ("Índice de protección", "IP65 resistente a chorros de agua y polvo"),
                ("Rango de voltaje", "100 - 277 VCA 50/60 Hz"),
                ("Norma aplicable", "NOM-030-ENER / NOM-064-SCFI")
            ]
        },
        {
            "archivo": "ficha_09_caja_registro_fs.pdf",
            "codigo": "CAJ-REG-FS075",
            "titulo": "Ficha Técnica: Caja de Registro Tipo FS de Aluminio Libre de Cobre 3/4 pulg",
            "fabricante": "Fundición Metálica Mayapán S.A. de C.V.",
            "descripcion": "Caja de registro serie rectangular de montaje superficial para uso pesado. Fabricada en aleación de aluminio libre de cobre con entradas roscadas NPT para conectar conduit metálico.",
            "especificaciones": [
                ("Medida de entradas", "3/4 de pulgada con rosca NPT cónica"),
                ("Número de entradas", "2 entradas (tipo pasante o ciega con tapón)"),
                ("Material de fabricación", "Aluminio inyectado a presión resistente a corrosión"),
                ("Empaque", "Neopreno troquelado para sellado hermético"),
                ("Uso", "Intemperie, bodegas industriales y áreas húmedas"),
                ("Tornillería", "Acero inoxidable calidad 304 incluida"),
                ("Norma oficial", "NOM-001-SEDE-2012 / NMX-J-023-ANCE")
            ]
        },
        {
            "archivo": "ficha_10_cinta_aislar_scotch.pdf",
            "codigo": "CON-CIN-3M1700",
            "titulo": "Ficha Técnica: Cinta Aislante de Vinilo Uso Profesional 19mm x 18m",
            "fabricante": "Distribuciones Técnicas del Mayab",
            "descripcion": "Cinta aislante de PVC con adhesivo a base de caucho sintético sensible a la presión. Posee excelente memoria elástica y resistencia a la abrasión, rayos UV, humedad, álcalis y ácidos.",
            "especificaciones": [
                ("Espesor total", "0.18 mm (7 mils)"),
                ("Ancho y largo", "19 mm de ancho x 18.3 metros de longitud"),
                ("Aislamiento dieléctrico", "Hasta 600 Volts continuos"),
                ("Rango de temperatura", "0 °C a 80 °C en operación continua"),
                ("Rigidez dieléctrica", "1,000 V/mil"),
                ("Resistencia a la flama", "Auto-extinguible según norma UL 510"),
                ("Norma aplicable", "NMX-J-541-ANCE / NOM-001-SEDE-2012")
            ]
        }
    ]
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1F497D')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555')
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13
    )

    for item in fichas_datos:
        ruta_pdf = FICHAS_DIR / item["archivo"]
        doc = SimpleDocTemplate(str(ruta_pdf), pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        
        # Encabezado
        story.append(Paragraph(item["titulo"], title_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>Código de producto:</b> {item['codigo']} | <b>Fabricante:</b> {item['fabricante']}", subtitle_style))
        story.append(Spacer(1, 12))
        
        # Descripción
        story.append(Paragraph("<b>Descripción General:</b>", subtitle_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(item["descripcion"], body_style))
        story.append(Spacer(1, 14))
        
        # Tabla de especificaciones
        story.append(Paragraph("<b>Especificaciones Técnicas Detalladas:</b>", subtitle_style))
        story.append(Spacer(1, 6))
        
        table_data = [["Parámetro", "Valor / Especificación"]]
        for k, v in item["especificaciones"]:
            table_data.append([k, v])
            
        t = Table(table_data, colWidths=[200, 320])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F497D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F5F9')]),
        ]))
        story.append(t)
        
        # Pie de página técnico
        story.append(Spacer(1, 16))
        story.append(Paragraph("<i>Documento técnico generado para el sistema de cotizaciones TESSERA · Proyecto Mérida, Yucatán.</i>", body_style))
        
        doc.build(story)
        fichas_generadas.append(item["archivo"])
        
    return fichas_generadas


# (codigo, servicio, tipo, unidad, precio, zona, incluir_en, dias_de_antiguedad, notas)
SERVICIOS_BASE = [
    ("SRV-FLE-MER", "Flete a obra en Mérida y zona conurbada", "Flete", "viaje", 650.00, "Mérida", "todos", 20, "Camioneta 3.5 t"),
    ("SRV-FLE-KAN", "Flete a obra en Kanasín", "Flete", "viaje", 780.00, "Kanasín", "todos", 35, "Camioneta 3.5 t"),
    ("SRV-FLE-UMA", "Flete a obra en Umán", "Flete", "viaje", 820.00, "Umán", "todos", 35, "Camioneta 3.5 t"),
    ("SRV-FLE-PRO", "Flete a obra en Progreso", "Flete", "viaje", 1150.00, "Progreso", "todos", 48, "Incluye maniobra de descarga"),
    ("SRV-FLE-MOT", "Flete a obra en Motul", "Flete", "viaje", 1350.00, "Motul", "todos", 245, "Tarifa por confirmar con transportista"),
    ("SRV-FLE-IZA", "Flete a obra en Izamal", "Flete", "viaje", 1650.00, "Izamal", "todos", 62, ""),
    ("SRV-FLE-VAL", "Flete a obra en Valladolid", "Flete", "viaje", 2400.00, "Valladolid", "todos", 230, "Tarifa de 2025"),
    ("SRV-FLE-TIZ", "Flete a obra en Tizimín", "Flete", "viaje", 2900.00, "Tizimín", "todos", 41, ""),
    ("SRV-INS-GAB", "Instalación de gabinete metálico (hasta 60 cm)", "Instalación", "pza", 480.00, "", "todos", 27, "Incluye fijación y nivelación"),
    ("SRV-INS-TAB", "Instalación de tablero o centro de carga", "Instalación", "pza", 650.00, "", "todos", 27, "No incluye acometida"),
    ("SRV-INS-CON", "Instalación de canalización con tubo conduit", "Instalación", "m", 38.00, "", "todos", 90, "Hasta 3 m de altura"),
    ("SRV-INS-LUM", "Instalación de luminaria industrial", "Instalación", "pza", 320.00, "", "todos", 215, "Tarifa de 2025"),
    ("SRV-INS-INT", "Instalación de interruptor termomagnético", "Instalación", "pza", 190.00, "", "todos", 27, ""),
    ("SRV-OPC-SUP", "Supervisión en obra (visita técnica)", "Opcional", "visita", 1800.00, "", "premium", 33, "Solo en escenario premium"),
    ("SRV-OPC-GAR", "Garantía extendida de 12 meses", "Opcional", "servicio", 2500.00, "", "premium", 33, "Solo en escenario premium"),
]


def generar_tarifario_csv() -> list[dict]:
    """Genera tarifario_servicios.csv: 15 filas válidas (sin defectos plantados), con suciedad de formato.

    Usa su propio generador aleatorio para no alterar los datos del catálogo, el historial ni las fichas.
    """
    rng = random.Random(SEMILLA + 7)
    filas = []
    for codigo, servicio, tipo, unidad, precio, zona, incluir_en, dias, notas in SERVICIOS_BASE:
        fecha = FECHA_REFERENCIA - timedelta(days=dias)
        filas.append({
            "Codigo": codigo,
            "Servicio": servicio,
            "Tipo": tipo,
            "Unidad": unidad,
            "Precio_Unitario": formatear_moneda(precio, rng.choice([0, 1, 2])),
            "Zona": zona,
            "Incluir_En": incluir_en,
            "Fecha_Precio": formatear_fecha(fecha, rng.choice([0, 1, 2])),
            "Notas": notas,
        })
    return filas


def escribir_tarifario() -> list[dict]:
    filas = generar_tarifario_csv()
    ruta = OUTPUT_DIR / "tarifario_servicios.csv"
    pd.DataFrame(filas).to_csv(ruta, index=False, encoding="utf-8")
    print(f"[OK] CSV generado: {ruta.name} ({len(filas)} filas, 0 defectuosas)")
    return filas


def actualizar_manifiesto_con_tarifario(filas: list[dict]) -> None:
    """Agrega la sección del tarifario al manifiesto existente sin tocar el resto (conteos del Hito 1 intactos)."""
    ruta = OUTPUT_DIR / "manifiesto.json"
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    manifiesto["resumen"]["total_archivos"] = 13
    manifiesto["resumen"]["tarifario_servicios"] = {
        "archivo": "tarifario_servicios.csv",
        "total_filas": len(filas),
        "filas_validas": len(filas),
        "filas_defectuosas": 0,
    }
    ruta.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Manifiesto actualizado con tarifario ({len(filas)} filas)")


def main():
    print("=" * 60)
    print("GENERADOR DE DATASET SINTÉTICO - TESSERA HITO 1")
    print(f"Semilla fija: {SEMILLA} | Fecha referencia: {FECHA_REFERENCIA.strftime('%Y-%m-%d')}")
    print("=" * 60)

    # 1. Catálogo CSV (50 filas)
    filas_csv, rechazos_csv = generar_catalogo_csv()
    df_csv = pd.DataFrame(filas_csv)
    ruta_csv = OUTPUT_DIR / "catalogo_materiales.csv"
    df_csv.to_csv(ruta_csv, index=False, encoding="utf-8")
    print(f"[OK] CSV generado: {ruta_csv.name} ({len(df_csv)} filas totales: {len(df_csv)-len(rechazos_csv)} válidas, {len(rechazos_csv)} defectuosas)")

    # 2. Historial XLSX (120 filas)
    filas_xlsx, rechazos_xlsx = generar_historial_xlsx()
    ruta_xlsx = OUTPUT_DIR / "historial_cotizaciones.xlsx"
    guardar_xlsx(filas_xlsx, ruta_xlsx)
    print(f"[OK] XLSX generado: {ruta_xlsx.name} ({len(filas_xlsx)} filas totales: {len(filas_xlsx)-len(rechazos_xlsx)} válidas, {len(rechazos_xlsx)} defectuosas)")

    # 3. Fichas técnicas en PDF (10 fichas)
    fichas_pdf = generar_fichas_pdf()
    print(f"[OK] 10 PDFs de fichas técnicas generados en: {FICHAS_DIR.name}/")

    # 3b. Tarifario de servicios (flete, instalación, opcionales premium)
    filas_tarifario = escribir_tarifario()

    # 4. Manifiesto
    todos_los_rechazos = rechazos_csv + rechazos_xlsx
    manifiesto = {
        "proyecto": "TESSERA",
        "hito": "HITO 1 · ENTRADA (DATOS)",
        "semilla": SEMILLA,
        "fecha_generacion": datetime.now().isoformat(),
        "resumen": {
            "total_archivos": 13,
            "catalogo_csv": {
                "archivo": "catalogo_materiales.csv",
                "total_filas": len(filas_csv),
                "filas_validas": len(filas_csv) - len(rechazos_csv),
                "filas_defectuosas": len(rechazos_csv)
            },
            "historial_xlsx": {
                "archivo": "historial_cotizaciones.xlsx",
                "total_filas": len(filas_xlsx),
                "filas_validas": len(filas_xlsx) - len(rechazos_xlsx),
                "filas_defectuosas": len(rechazos_xlsx)
            },
            "fichas_pdf": {
                "total_archivos": len(fichas_pdf),
                "validos": len(fichas_pdf),
                "defectuosos": 0
            },
            "tarifario_servicios": {
                "archivo": "tarifario_servicios.csv",
                "total_filas": len(filas_tarifario),
                "filas_validas": len(filas_tarifario),
                "filas_defectuosas": 0
            },
            "totales_combinados": {
                "total_filas_datos": len(filas_csv) + len(filas_xlsx),
                "total_filas_validas": (len(filas_csv) - len(rechazos_csv)) + (len(filas_xlsx) - len(rechazos_xlsx)),
                "total_filas_defectuosas": len(todos_los_rechazos)
            }
        },
        "rechazos_plantados": todos_los_rechazos
    }

    ruta_manifiesto = OUTPUT_DIR / "manifiesto.json"
    with open(ruta_manifiesto, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, indent=2, ensure_ascii=False)
    print(f"[OK] Manifiesto guardado: {ruta_manifiesto.name} ({len(todos_los_rechazos)} rechazos plantados documentados)")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if "--solo-tarifario" in sys.argv:
        actualizar_manifiesto_con_tarifario(escribir_tarifario())
    else:
        main()
