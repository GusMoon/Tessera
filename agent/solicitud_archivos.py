"""Convierte los archivos adjuntos de una solicitud (PDF, Excel, CSV, texto de chat) en el texto que entiende el intérprete.

Es determinista y no usa el modelo: lee tablas («Concepto | Cantidad | Unidad»), celdas de PDF una por línea, mensajes de
chat con marca de hora y frases de servicio («flete a Progreso», «con instalación»). Lo que no reconoce se descarta y se
avisa; nunca se inventa un renglón. El intérprete (`agent/interpretar.py`) sigue siendo quien resuelve cada renglón contra
el catálogo y pregunta lo que falte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent.llm.adjuntos import Adjunto

MAX_RENGLONES = 200
_SERVICIO = re.compile(r"instalaci|flete|entrega\s+en|env[ií]o\s+a|\bllev(?:an|en|amos|ar)\b|\bviajes?\b", re.IGNORECASE)
_ENCABEZADO_CONCEPTO = ("concepto", "descripcion", "descripción", "material", "articulo", "artículo", "producto", "detalle")
_ENCABEZADO_CANTIDAD = ("cantidad", "cant", "cant.", "piezas", "qty")
_ENCABEZADO_UNIDAD = ("unidad", "um", "u.m.")
_MARCA_CHAT = re.compile(r"^\s*\[?\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\]?\s*(?:-\s*)?(?P<resto>.*)$")
_REMITENTE = re.compile(r"^(?P<nombre>[^:()]{1,40})(?:\((?P<empresa>[^)]{2,60})\))?\s*:\s*(?P<texto>.*)$")
_CLIENTE_EXPLICITO = re.compile(r"\b(?:cliente|empresa|obra|proyecto)\s*[:：]\s*([^\n|·.;]{3,70})", re.IGNORECASE)
_TITULO_NO_CLIENTE = re.compile(r"solicitud|pedido|cotiz|lista|orden|hoja|presupuesto|material", re.IGNORECASE)
_CANTIDAD_UNIDAD = re.compile(r"^\s*(\d[\d,]*)\s*([A-Za-zÁÉÍÓÚáéíóúñ.]{0,14})\s*$")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


@dataclass
class SolicitudDeArchivos:
    texto: str  # lo que se le entrega al intérprete (renglones y frases de servicio)
    cliente: str | None = None
    avisos: list[str] = field(default_factory=list)
    renglones: int = 0  # cuántos renglones de material se reconocieron en los archivos


def _limpiar(linea: str) -> str:
    return re.sub(r"\s+", " ", _EMOJI.sub("", linea)).strip(" \t|·")


def _entero(texto: str) -> int | None:
    t = texto.replace(",", "").strip()
    return int(t) if re.fullmatch(r"\d+", t) else None


def _columnas(celdas: list[str]) -> dict[str, int] | None:
    """Índice de las columnas de concepto, cantidad y unidad si la fila es un encabezado de tabla."""
    minusculas = [c.strip().lower() for c in celdas]
    concepto = next((i for i, c in enumerate(minusculas) if c in _ENCABEZADO_CONCEPTO), None)
    cantidad = next((i for i, c in enumerate(minusculas) if c in _ENCABEZADO_CANTIDAD), None)
    if concepto is None or cantidad is None:
        return None
    unidad = next((i for i, c in enumerate(minusculas) if c in _ENCABEZADO_UNIDAD), None)
    return {"concepto": concepto, "cantidad": cantidad, **({"unidad": unidad} if unidad is not None else {})}


def _renglon(cantidad: int, unidad: str, concepto: str) -> str:
    unidad = unidad.strip(". ")
    return f"{cantidad} {unidad} de {concepto}" if unidad else f"{cantidad} {concepto}"


def _sin_conjuncion_inicial(texto: str) -> str:
    return re.sub(r"^(?:y|e|además|ademas|también|tambien)\s+", "", texto.strip(), flags=re.IGNORECASE)


def _expandir_alcance(clausula: str) -> list[str]:
    """«instalación incluida de gabinetes y canalización» → «instalación de gabinetes», «instalación de canalización»."""
    m = re.search(r"(instalaci[oó]n(?:\s+(?:incluida|incluido))?)\s+de\s+(?:los\s+|las\s+)?(.+)$", clausula, re.IGNORECASE)
    if not m:
        return [clausula]
    alcances = [a.strip() for a in re.split(r"\s*,\s*|\s+y\s+", m.group(2)) if a.strip()]
    if len(alcances) < 2:
        return [clausula]
    return [f"instalación de {a}" for a in alcances]


def _clausulas_de_servicio(frase: str) -> list[str]:
    """De un párrafo se conservan solo las cláusulas que hablan de instalación, flete o entrega (sin dos puntos: el
    intérprete toma lo anterior al primer «:» como encabezado y lo descarta)."""
    salida: list[str] = []
    for oracion in re.split(r"[;.]\s+|[;.]$", frase):
        oracion = re.sub(r"^[\wáéíóúñ ]{1,20}:\s*", "", oracion.strip())  # «Condiciones: …»
        if not oracion or not _SERVICIO.search(oracion):
            continue
        trozos = [oracion] if len(oracion) <= 80 else [t for t in oracion.split(",") if _SERVICIO.search(t)]
        for t in trozos:
            salida += _expandir_alcance(_sin_conjuncion_inicial(t.replace(":", " ")))
    return salida


def _cliente_de_titulo(primera: str) -> str | None:
    candidato = re.sub(r"\([^)]*\)", "", primera.split("·")[0]).strip(" .:-")
    if not (3 <= len(candidato) <= 60) or _TITULO_NO_CLIENTE.search(candidato) or re.search(r"\d", candidato):
        return None
    return candidato.title() if candidato.isupper() else candidato


def _desde_tabla(lineas: list[str]) -> tuple[list[str], list[str], str | None]:
    """Filas «a | b | c»: devuelve (renglones, frases de servicio sin cantidad, cliente de la columna Obra/Cliente)."""
    columnas = None
    renglones: list[str] = []
    servicios: list[str] = []
    cliente = None
    indice_cliente = None
    for linea in lineas:
        celdas = [c.strip() for c in linea.split("|")]
        if columnas is None:
            columnas = _columnas(celdas)
            if columnas:
                indice_cliente = next((i for i, c in enumerate(celdas) if c.strip().lower() in ("obra", "cliente", "empresa", "proyecto")), None)
            continue
        if len(celdas) <= max(columnas.values()):
            continue
        concepto = _limpiar(celdas[columnas["concepto"]])
        if not concepto:
            continue
        if indice_cliente is not None and not cliente and indice_cliente < len(celdas) and celdas[indice_cliente].strip():
            cliente = celdas[indice_cliente].strip()
        cantidad = _entero(celdas[columnas["cantidad"]])
        unidad = _limpiar(celdas[columnas["unidad"]]) if "unidad" in columnas and columnas["unidad"] < len(celdas) else ""
        if cantidad:
            renglones.append(_renglon(cantidad, unidad, concepto))
        elif _SERVICIO.search(concepto):
            servicios.append(concepto)
    return renglones, servicios, cliente


def _desde_celdas_de_pdf(lineas: list[str]) -> tuple[list[str], list[str]]:
    """pypdf entrega cada celda en su línea: «1», «Gabinete …», «12 piezas». Devuelve (renglones, líneas que no eran celdas)."""
    renglones: list[str] = []
    resto: list[str] = []
    i = 0
    while i < len(lineas):
        if i + 2 < len(lineas):
            a, b, c = lineas[i], lineas[i + 1], lineas[i + 2]
            m = _CANTIDAD_UNIDAD.match(c)
            if re.fullmatch(r"\d{1,3}", a) and m and not _CANTIDAD_UNIDAD.match(b) and len(b) > 3:
                renglones.append(_renglon(int(m.group(1).replace(",", "")), m.group(2), _limpiar(b)))
                i += 3
                continue
        resto.append(lineas[i])
        i += 1
    return renglones, resto


def _unir_lineas_cortadas(lineas: list[str]) -> list[str]:
    """Un párrafo de PDF viene partido en renglones: se une la línea que no termina en punto con la siguiente."""
    unidas: list[str] = []
    for l in lineas:
        if unidas and not re.search(r"[.;:!?]$", unidas[-1]):
            unidas[-1] += " " + l
        else:
            unidas.append(l)
    return unidas


def _desde_chat(lineas: list[str]) -> tuple[list[str], str | None, bool]:
    """Mensajes «[18/11/2026 09:12] Nombre (Empresa): texto»: se queda el texto y, si hay, la empresa del remitente."""
    cuerpo: list[str] = []
    empresa = None
    es_chat = False
    for linea in lineas:
        m = _MARCA_CHAT.match(linea)
        if not m:
            cuerpo.append(linea)
            continue
        es_chat = True
        r = _REMITENTE.match(m.group("resto").strip())
        if r:
            empresa = empresa or (r.group("empresa") or "").strip() or None
            cuerpo.append(r.group("texto"))
        else:
            cuerpo.append(m.group("resto"))
    return cuerpo, empresa, es_chat


_PALABRAS_NUMERO = "un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|doce|quince|veinte|treinta|cuarenta|cincuenta|cien|media|docena"
# Un renglón de texto libre empieza con la cantidad (tras a lo más tres palabras de relleno, como «ocupo» o «necesito»)
# y le sigue una palabra del material. «$150,000.00», «15%», «30 días» o una fecha no son cantidades de material.
_RENGLON_LIBRE = re.compile(
    rf"^(?:[A-Za-zÁÉÍÓÚáéíóúñ]+\s+){{0,3}}?(?:\d{{1,6}}|{_PALABRAS_NUMERO})\s+"
    r"(?!(?:d[ií]as?|mes(?:es)?|a[ñn]os?|horas?|semanas?|pesos|mxn)\b)[A-Za-zÁÉÍÓÚáéíóúñ0-9]",
    re.IGNORECASE,
)


def _es_renglon_libre(linea: str) -> bool:
    if re.search(r"[$%]|\bmxn\b|\d{1,2}/\d{1,2}/\d{2,4}", linea, re.IGNORECASE) or _SERVICIO.search(linea):
        return False
    return bool(_RENGLON_LIBRE.match(linea))


def _parece_lista_de_precios(texto: str) -> bool:
    encabezado = texto.splitlines()[0].lower() if texto.strip() else ""
    return "precio" in encabezado and any(p in encabezado for p in ("sku", "codigo", "código", "descripcion", "descripción"))


@dataclass
class _LecturaArchivo:
    renglones: list[str] = field(default_factory=list)
    frases: list[str] = field(default_factory=list)
    cliente: str | None = None


def _leer_archivo(a: Adjunto) -> _LecturaArchivo:
    """Renglones, frases de servicio y cliente de un archivo. Si no trae renglones con cantidad no aporta nada: ni sus frases
    ni su cliente (una política o una lista de precios no es una solicitud)."""
    crudo = [_limpiar(l) for l in a.texto.splitlines()]
    crudo = [l for l in crudo if l and not l.startswith("## Hoja:")]
    lectura = _LecturaArchivo()
    if not crudo:
        return lectura
    cliente = None
    if sum(1 for l in crudo if "|" in l) >= 2:
        lectura.renglones, servicios, cliente = _desde_tabla([l for l in a.texto.splitlines() if "|" in l])
        lectura.frases += servicios
        cuerpo = [l for l in crudo if "|" not in l]
    else:
        cuerpo, cliente, es_chat = _desde_chat(crudo)
        lectura.renglones, cuerpo = _desde_celdas_de_pdf(cuerpo)
        if not es_chat:
            cuerpo = _unir_lineas_cortadas(cuerpo)
        if not lectura.renglones:  # texto libre: cada línea que empieza con una cantidad es un renglón
            lectura.renglones = [_sin_conjuncion_inicial(l) for l in cuerpo if _es_renglon_libre(l)]
    if not lectura.renglones:
        return _LecturaArchivo()

    # frases de servicio y cliente salen de todo el texto (párrafos, condiciones, mensajes de chat)
    for l in cuerpo:
        for c in _clausulas_de_servicio(l):
            if c not in lectura.frases:
                lectura.frases.append(c)
    if not cliente:
        for l in crudo:
            m = _CLIENTE_EXPLICITO.search(l)
            if m:
                cliente = m.group(1).strip()
                break
    lectura.cliente = cliente or _cliente_de_titulo(crudo[0])
    lectura.renglones = [r.replace(":", " ") for r in lectura.renglones]
    return lectura


def preparar_solicitud(mensaje: str, adjuntos: list[Adjunto]) -> SolicitudDeArchivos:
    """Une lo que escribió el usuario con lo que dicen sus archivos de texto. Las imágenes no se leen aquí."""
    renglones: list[str] = []
    frases: list[str] = []
    avisos: list[str] = []
    clientes: list[str] = []

    for a in adjuntos:
        if a.tipo != "texto":
            continue
        lectura = _leer_archivo(a)
        if not lectura.renglones:
            if _parece_lista_de_precios(a.texto):
                avisos.append(f"{a.nombre} parece una lista de precios, no una solicitud: se carga en Fuentes (como Administrador) y no se adjunta al chat.")
            else:
                avisos.append(f"No reconocí renglones con cantidad en {a.nombre}. Si es un catálogo, una ficha o un documento interno, se carga en Fuentes, no se adjunta al chat.")
            continue
        renglones += lectura.renglones
        frases += [f for f in lectura.frases if f not in frases]
        if lectura.cliente:
            clientes.append(lectura.cliente)

    distintos = list(dict.fromkeys(clientes))
    if len(distintos) > 1:
        avisos.append(f"Los archivos parecen de clientes distintos ({', '.join(distintos)}) y se juntaron en una sola cotización a nombre de {distintos[0]}. Si son pedidos separados, cotízalos por separado.")

    if len(renglones) > MAX_RENGLONES:
        avisos.append(f"Solo se leyeron los primeros {MAX_RENGLONES} renglones de los archivos.")
        renglones = renglones[:MAX_RENGLONES]

    # El mensaje del usuario cuenta como solicitud solo si trae cantidades o servicios; «hazlo con los archivos» es una instrucción.
    propio = mensaje.strip()
    lleva_datos = bool(re.search(r"\d", propio) or _SERVICIO.search(propio))
    partes = ([propio] if propio and (lleva_datos or not renglones) else []) + renglones + [f for f in frases if f not in propio]
    texto = ".\n".join(p.rstrip(".") for p in partes if p) + ("." if partes else "")
    return SolicitudDeArchivos(texto=texto, cliente=distintos[0] if distintos else None, avisos=avisos, renglones=len(renglones))
