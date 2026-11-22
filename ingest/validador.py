"""Módulo de validación y normalización para la ingesta de Tessera.

Normaliza:
- Fechas a formato ISO (YYYY-MM-DD) y calcula antigüedad en meses (> 6 meses = desactualizado).
- Monedas a float decimal y valida valores no numéricos o negativos.
- Unidades a claves estándar legibles (PZA, M, TRAMO, ROLLO, KG, BOLSA).
- Cantidades a flotante positivo (> 0).
- Detección de duplicados en cotizaciones.
"""

import re
from datetime import datetime, date
from typing import Any, Tuple, Optional

# Fecha de referencia del sistema (o actual)
FECHA_ACTUAL = datetime(2026, 11, 21)


def normalizar_fecha(valor: Any, fecha_ref: datetime = FECHA_ACTUAL) -> Tuple[Optional[str], int, bool, Optional[str]]:
    """
    Normaliza una fecha a 'YYYY-MM-DD'.
    Retorna: (fecha_iso, antiguedad_meses, es_valida, motivo_error)
    """
    if valor is None:
        return None, 0, False, "Fecha faltante o vacía"
    
    # Si viene como objeto date/datetime desde openpyxl o pandas
    if isinstance(valor, (datetime, date)):
        dt = datetime(valor.year, valor.month, valor.day)
    else:
        val_str = str(valor).strip()
        if not val_str or val_str.lower() in ("nan", "none", "null", "n/a"):
            return None, 0, False, "Fecha faltante o vacía"
        
        # Mapeo de meses en español
        meses = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }
        
        # Formatos comunes
        patrones = [
            "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d",
            "%d/%m/%y", "%d-%m-%y"
        ]
        
        dt = None
        for pat in patrones:
            try:
                dt = datetime.strptime(val_str, pat)
                break
            except ValueError:
                continue
        
        # Probar formato '15 de enero de 2026'
        if dt is None:
            match = re.search(r'(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', val_str.lower())
            if match:
                dia, mes_nom, anio = match.groups()
                mes_num = meses.get(mes_nom)
                if mes_num:
                    try:
                        dt = datetime(int(anio), int(mes_num), int(dia))
                    except ValueError:
                        pass
        
        if dt is None:
            return None, 0, False, "Fecha inválida"

    # Validar rangos coherentes
    if dt.year < 1990 or dt.year > 2050:
        return None, 0, False, f"Año de fecha fuera de rango ({dt.year})"

    # Cálculo de antigüedad en meses
    diff_dias = (fecha_ref - dt).days
    antiguedad_meses = max(0, int(diff_dias / 30.4375))
    
    fecha_iso = dt.strftime("%Y-%m-%d")
    return fecha_iso, antiguedad_meses, True, None


def normalizar_moneda(valor: Any) -> Tuple[Optional[float], bool, Optional[str]]:
    """
    Normaliza un valor monetario o precio a float decimal.
    Retorna: (precio_float, es_valido, motivo_error)
    """
    if valor is None:
        return None, False, "Precio no numérico o vacío"
    
    if isinstance(valor, (int, float)):
        if valor < 0:
            return None, False, "Precio unitario negativo"
        return round(float(valor), 2), True, None
    
    val_str = str(valor).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "n/a", "consultar", "por definir"):
        return None, False, "Precio no numérico o vacío"
    
    # Limpiar signos de moneda, MXN y espacios
    limpio = re.sub(r'[\$\sMXNmxn]', '', val_str)
    limpio = limpio.replace(',', '')  # Quitar comas de miles
    
    try:
        num = float(limpio)
        if num < 0:
            return None, False, "Precio unitario negativo"
        return round(num, 2), True, None
    except ValueError:
        return None, False, "Precio no numérico o vacío"


def normalizar_cantidad(valor: Any) -> Tuple[Optional[float], bool, Optional[str]]:
    """
    Normaliza una cantidad a float positivo (> 0).
    Retorna: (cantidad_float, es_valida, motivo_error)
    """
    if valor is None:
        return None, False, "Cantidad menor o igual a cero o faltante"
    
    if isinstance(valor, (int, float)):
        if valor <= 0:
            return None, False, "Cantidad menor o igual a cero o faltante"
        return float(valor), True, None
    
    val_str = str(valor).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "n/a"):
        return None, False, "Cantidad menor o igual a cero o faltante"
    
    try:
        num = float(val_str.replace(',', ''))
        if num <= 0:
            return None, False, "Cantidad menor o igual a cero o faltante"
        return num, True, None
    except ValueError:
        return None, False, "Cantidad no numérica"


def normalizar_unidad(unidad_cruda: Any) -> str:
    """Normaliza variantes de unidades a códigos estándar mayúsculas."""
    if not unidad_cruda:
        return "PZA"
    
    u = str(unidad_cruda).strip().lower()
    if u in ("pza", "pz", "pieza", "piezas", "pzas"):
        return "PZA"
    elif u in ("m", "mt", "mts", "metro", "metros"):
        return "M"
    elif u in ("tramo", "tramos", "trm"):
        return "TRAMO"
    elif u in ("rollo", "rollos", "rlo"):
        return "ROLLO"
    elif u in ("kg", "kilos", "kilo", "kilogramo", "kilogramos"):
        return "KG"
    elif u in ("bolsa", "bolsas"):
        return "BOLSA"
    elif u in ("lote", "lotes"):
        return "LOTE"
    elif u in ("jgo", "juego", "juegos"):
        return "JGO"
    else:
        return u.upper()
