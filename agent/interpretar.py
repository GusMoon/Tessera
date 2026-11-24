"""Intérprete DETERMINISTA de solicitudes de cotización (el camino que se mide en el Hito 2; no usa LLM).

Convierte «20 gabinetes NEMA 4X y 100 rollos de cable THW calibre 12 negro, con instalación y flete a Umán» en
renglones del catálogo y servicios del tarifario, resueltos con la búsqueda híbrida (`retrieval`) y con los
permisos del usuario. Si falta algo o es ambiguo, **pregunta** en lugar de inventar (regla 2 de CLAUDE.md).

Reglas de negocio sintéticas que el equipo debe validar (decisión abierta 3 y roles A/E):
- El precio del catálogo es el costo; los márgenes los pone `calcular_cotizacion`.
- La instalación se cotiza por categoría de material (`INSTALACION_POR_CATEGORIA`) con la tarifa del tarifario.
- El flete es un viaje a la zona mencionada (o N viajes si se indican).
- Los servicios opcionales del tarifario con `incluir_en = premium` entran solo al escenario premium.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from agent.tools.buscar_precios import a_centavos, buscar_precios
from agent.tools.calcular_cotizacion import Linea
from retrieval.embeddings import normalizar_texto
from retrieval.indice import Indice

# --------------------------------------------------------------------------- vocabulario
NUMEROS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500,
}
DECENAS = "treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa"
UNIDADES = "uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve"
UNIDADES_GENERICAS = {"pieza", "piezas", "pza", "pzas", "pz", "pzs", "unidad", "unidades"}
UNIDAD_CANONICA = {
    "rollo": "ROLLO", "rollos": "ROLLO", "tramo": "TRAMO", "tramos": "TRAMO", "bolsa": "BOLSA", "bolsas": "BOLSA",
    "metro": "M", "metros": "M", "mts": "M", "mt": "M", "m": "M",
}
RELLENO_INICIAL = frozenset(
    "necesito necesitamos necesita quiero queremos requiero requerimos ocupo ocupamos solicito solicitamos cotiza cotizar "
    "cotizame cotizanos cotizacion presupuesto precio precios favor por de del para me nos pueden puedes podrias "
    "podrian ayudas ayudan con la el los las obra pedido material materiales lista siguiente incluye incluyendo "
    "ademas tambien hola buenos dias tardes se oye sobre si requieren requiere necesitan ocupan solicitan quisiera "
    "quisieramos agregar agrega incluir anota pon ponme dame dar hazme hacer cotizaciones amablemente".split()
)
SINONIMOS = {
    "pulgada": "pulg", "pulgad": "pulg", "pulg": "pulg", "tablero": "centro", "conductor": "cable", "alambre": "cable",
    "lampara": "luminaria", "foco": "luminaria", "pastilla": "interruptor", "cal": "calibre", "pvc": "pvc",
    "termomagnetico": "termomagnetico", "mts": "m", "pzas": "pza",
}
PALABRAS_SERVICIO = {
    "instalacion": r"\b(instalacion|instalar|instalado|instalados|instaladas?|colocacion|montaje)\b",
    "flete": r"\b(flete|fletes|envio|envios|transporte|entrega|entregar|entregado|enviar|llevar|llevan|lleven|llevamos|acarreo)\b",
    "opcional": r"\b(supervision|garantia)\b",
}
PALABRAS_DESTINO = r"\b(flete|envio|transporte|entrega|entregar|enviar|llevar|llevan|lleven|llevamos|obra|domicilio|sitio|destino|acarreo)\b"
INSTALACION_POR_CATEGORIA = {  # categoría (sin acentos, minúsculas) → código del tarifario
    "gabinetes": "SRV-INS-GAB", "tableros": "SRV-INS-TAB", "canalizacion": "SRV-INS-CON",
    "iluminacion": "SRV-INS-LUM", "proteccion": "SRV-INS-INT",
}
ALCANCE_INSTALACION = {  # palabra en «instalación de …» → categoría
    r"\bgabinete": "gabinetes", r"\b(tablero|centro de carga|centros de carga)": "tableros",
    r"\b(conduit|tubo|tubos|canalizacion|tuberia)": "canalizacion", r"\b(luminaria|lampara|reflector)": "iluminacion",
    r"\b(interruptor|pastilla|termomagnetico)": "proteccion",
}
COBERTURA_MINIMA = 0.5
COBERTURA_SUGERENCIA = 0.2  # por debajo de esto un candidato no se ofrece como «¿te refieres a…?»
_COLA = r"(?:\s+(?:incluida|incluido|incluidas|incluidos|incluye|incluyendo|completa|completo))?"
_FIN = r"(?=$|[,;.]|\s+y\s|\s+e\s)"
_ALCANCE = r"(?:\s+(?:de|del)\s+(?:(?:los|las|el|la|unos|unas)\s+)?%s)?"
INSTALACION_CON_ALCANCE = PALABRAS_SERVICIO["instalacion"] + _COLA + _ALCANCE % "([a-z0-9 ]*?)" + _FIN
INSTALACION_SIN_CAPTURA = PALABRAS_SERVICIO["instalacion"] + _COLA + _ALCANCE % "[a-z0-9 ]*?" + _FIN


# --------------------------------------------------------------------------- resultado
@dataclass
class Interpretacion:
    lineas: list[Linea] = field(default_factory=list)
    preguntas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    renglones: list[dict] = field(default_factory=list)  # rastro de cómo se resolvió cada renglón
    cliente: str | None = None
    zona: str | None = None
    instalacion: bool = False

    @property
    def completa(self) -> bool:
        return not self.preguntas and any(l.tipo == "material" for l in self.lineas)


# --------------------------------------------------------------------------- utilidades de texto
def tokens_comparacion(texto: str) -> list[str]:
    """Palabras y cifras de comparación: separa letras de números («30a» → 30, a), quita plurales y unifica sinónimos."""
    t = normalizar_texto(texto)
    crudos = re.findall(r"\d+/\d+|\d+(?:\.\d+)?|[a-z]+", t)
    salida = []
    for tok in crudos:
        if len(tok) == 1 and not tok.isdigit():
            continue
        if len(tok) > 4 and tok.endswith("es") and tok[:-2] in {"interruptor", "conector", "reflector", "conductor", "tablero"}:
            tok = tok[:-2]
        elif len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        salida.append(SINONIMOS.get(tok, tok))
    return salida


def cobertura(consulta: list[str], candidato: list[str]) -> float:
    """Fracción de las palabras de la consulta que aparecen en el candidato."""
    if not consulta:
        return 0.0
    conjunto = set(candidato)
    return sum(1 for t in consulta if t in conjunto) / len(consulta)


def _numeros_compuestos(t: str) -> str:
    """«treinta y cinco» → «35» antes de partir por « y »."""
    def suma(m: re.Match) -> str:
        return str(NUMEROS[m.group(1)] + NUMEROS[m.group(2)])
    t = re.sub(rf"\b({DECENAS})\s+y\s+({UNIDADES})\b", suma, t)
    t = re.sub(r"\bmedia docena\b", "6", t)
    return re.sub(r"\b(\d+|" + "|".join(NUMEROS) + r")\s+docenas?\b",
                  lambda m: str((int(m.group(1)) if m.group(1).isdigit() else NUMEROS[m.group(1)]) * 12), t)


def _leer_cantidad(seg: str) -> tuple[int | None, str, str | None, str | None]:
    """(cantidad, resto, unidad_escrita, problema). Acepta «20», «veinte», «un/una» y unidades («rollos», «piezas»)."""
    seg = seg.strip()
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*(?:x\b)?\s*", seg)
    cantidad: int | None = None
    problema = None
    if m:
        bruto = m.group(1).replace(",", ".")
        valor = float(bruto)
        if valor != int(valor) or valor < 1:
            problema = f"La cantidad «{m.group(1)}» debe ser un número entero de piezas, rollos o tramos."
        else:
            cantidad = int(valor)
        seg = seg[m.end():]
    else:
        m = re.match(r"^(" + "|".join(sorted(NUMEROS, key=len, reverse=True)) + r")\b\s*", seg)
        if m:
            cantidad = NUMEROS[m.group(1)]
            seg = seg[m.end():]
    unidad = None
    mu = re.match(r"^(" + "|".join(sorted(list(UNIDADES_GENERICAS) + list(UNIDAD_CANONICA), key=len, reverse=True)) + r")\b\.?\s*(?:de\s+)?", seg)
    if cantidad is not None and mu:
        unidad = mu.group(1)
        seg = seg[mu.end():]
    return cantidad, seg.strip(), unidad, problema


def _quitar_relleno(seg: str) -> str:
    palabras = seg.split()
    while palabras and palabras[0] in RELLENO_INICIAL:
        palabras.pop(0)
    return " ".join(palabras)


# --------------------------------------------------------------------------- tarifario
def servicios_visibles(conn: sqlite3.Connection, usuario_id: str) -> list[dict]:
    """Servicios del tarifario que el usuario puede abrir (permiso de la fuente resuelto en SQL)."""
    from retrieval.permisos import permisos_de

    permisos = sorted(permisos_de(usuario_id, conn))
    filas = conn.execute(
        f"""SELECT s.codigo, s.servicio, s.tipo, s.unidad, s.precio_unitario, s.zona, s.incluir_en, s.fecha_precio, s.antiguedad_meses
            FROM servicios s JOIN fuentes f ON f.id = s.fuente_id
            WHERE f.permiso IN ({','.join('?' * len(permisos))}) ORDER BY s.id""",
        permisos,
    ).fetchall()
    return [dict(f) for f in filas]


def _linea_servicio(s: dict, cantidad: int) -> Linea:
    return Linea(
        tipo="servicio", codigo=s["codigo"], concepto=s["servicio"], unidad=s["unidad"], cantidad=cantidad,
        costo_unitario_centavos=a_centavos(s["precio_unitario"]), fuente_ref=f"servicio:{s['codigo']}",
        fuente_fecha=s["fecha_precio"], antiguedad_meses=s["antiguedad_meses"] or 0, incluir_en=s["incluir_en"],
    )


# --------------------------------------------------------------------------- servicios pedidos en el texto
def _extraer_servicios(t: str, zonas: dict[str, str]) -> tuple[str, dict]:
    """Quita del texto lo que habla de flete, instalación y opcionales; devuelve lo demás y lo detectado."""
    info = {"instalacion": False, "alcance": set(), "flete": False, "flete_explicito": False, "zona": None, "viajes": 1}

    for nombre_norm, nombre in zonas.items():
        if re.search(rf"\b{re.escape(nombre_norm)}\b", t):
            info["zona"] = nombre
            break
    if info["zona"]:
        info["flete"] = True  # la zona mencionada es el destino; `interpretar` avisa para que se pueda quitar

    m = re.search(r"(\d+)\s+viajes?\b", t)
    if m:
        info["viajes"] = max(1, int(m.group(1)))

    for m in re.finditer(INSTALACION_CON_ALCANCE, t):
        info["instalacion"] = True
        for patron, categoria in ALCANCE_INSTALACION.items():
            if m.group(2) and re.search(patron, m.group(2)):
                info["alcance"].add(categoria)

    if re.search(PALABRAS_SERVICIO["flete"], t):
        info["flete"] = True
        info["flete_explicito"] = True

    # Se elimina el texto de servicios para que no se confunda con materiales.
    t = re.sub(INSTALACION_SIN_CAPTURA, " ", t)
    t = re.sub(PALABRAS_SERVICIO["opcional"] + r"[a-z ]*?(?=$|[,;.]|\s+y\s)", " ", t)
    zona_re = "|".join(re.escape(z) for z in zonas) or "(?!x)x"
    t = re.sub(rf"\b(?:{PALABRAS_SERVICIO['flete'][3:-3]})\b(?:\s+(?:a|en|hacia|para|de)(?:\s+(?:la|el|obra|sitio))*)?(?:\s+(?:{zona_re}))?(?:\s+\d+\s+viajes?)?", " ", t)
    t = re.sub(rf"\b(?:(?:obra|entrega|domicilio|sitio)\s+)?(?:(?:para|en|a|hacia|de)\s+)?(?:{zona_re})\b", " ", t)
    t = re.sub(r"\b\d+\s+viajes?\b", " ", t)
    return t, info


def _cliente(texto: str) -> str | None:
    m = re.search(r"\b[Pp]ara\s+(?:la\s+|el\s+)?((?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.&-]*\s?){1,6})\s*[:,]", texto)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------------------- resolución de un renglón
def _resolver_renglon(
    conn: sqlite3.Connection, indice: Indice, descripcion: str, usuario_id: str, vector: np.ndarray | None
) -> tuple[dict | None, list[dict], str | None]:
    """(elegido, candidatos, motivo_si_no_se_pudo). Decide por cobertura léxica de los candidatos de la búsqueda híbrida."""
    candidatos = buscar_precios(conn, indice, descripcion, usuario_id, k=5, tipos=("catalogo",), vector=vector)
    if not candidatos:
        return None, [], "sin_resultados"
    consulta = tokens_comparacion(descripcion)
    puntuados = []
    for c in candidatos:
        toks = tokens_comparacion(f"{c['concepto']} {c['categoria'] or ''}")
        c["cobertura"] = cobertura(consulta, toks)
        puntuados.append(c)
    mejor = max(c["cobertura"] for c in puntuados)
    if mejor < COBERTURA_MINIMA:
        return None, puntuados, "sin_coincidencia"
    empatados = [c for c in puntuados if abs(c["cobertura"] - mejor) < 1e-9]
    if len(empatados) > 1:
        return None, empatados, "ambiguo"
    return empatados[0], puntuados, None


PALABRAS_VACIAS = frozenset({"de", "del", "la", "el", "los", "las", "con", "para", "por", "sin", "una", "uno", "pulg", "unidad", "pieza"})


def _se_parece(descripcion: str, candidato: dict) -> bool:
    """Un candidato se ofrece como sugerencia solo si comparte una palabra con contenido («kilos de cemento» no se parece a
    «centro de carga» por el «de»)."""
    utiles = {w for w in tokens_comparacion(descripcion) if len(w) >= 4 and w not in PALABRAS_VACIAS}
    suyas = set(tokens_comparacion(f"{candidato['concepto']} {candidato.get('categoria') or ''}"))
    return bool(utiles & suyas) and candidato.get("cobertura", 0) >= COBERTURA_SUGERENCIA


def _lo_que_cubre(conn: sqlite3.Connection, usuario_id: str) -> str:
    """Cuando nada se parece, se dice qué categorías sí hay en lugar de proponer artículos sin relación."""
    from retrieval.permisos import permisos_de

    permisos = sorted(permisos_de(usuario_id, conn))
    filas = conn.execute(
        f"SELECT DISTINCT c.categoria FROM catalogo c JOIN fuentes f ON f.id = c.fuente_id "  # noqa: S608
        f"WHERE f.permiso IN ({','.join('?' for _ in permisos)}) AND c.categoria IS NOT NULL ORDER BY c.categoria", permisos,
    ).fetchall()
    categorias = [f[0] for f in filas if f[0]]
    return f" El catálogo cargado cubre: {', '.join(categorias)}." if categorias else ""


# --------------------------------------------------------------------------- interpretación completa
def interpretar(
    solicitud: str, conn: sqlite3.Connection, indice: Indice, usuario_id: str, incluir_opcionales: bool = True
) -> Interpretacion:
    """Convierte la solicitud en `Interpretacion.lineas` (materiales + servicios) o en `preguntas` concretas."""
    res = Interpretacion(cliente=_cliente(solicitud))
    servicios = servicios_visibles(conn, usuario_id)
    zonas = {normalizar_texto(s["zona"]): s["zona"] for s in servicios if s["zona"]}

    t = _numeros_compuestos(normalizar_texto(solicitud))
    if res.cliente:  # «para Constructora Kanasín:» nombra al cliente, no el destino
        t = t.replace("para " + normalizar_texto(res.cliente), " ", 1)
    t, info = _extraer_servicios(t, zonas)
    if ":" in t:
        t = t.split(":", 1)[1]  # lo anterior a los dos puntos es el encabezado de la solicitud
    res.instalacion = info["instalacion"]
    res.zona = info["zona"]

    segmentos = [s for s in re.split(r"\s*(?:[,;\n]|\by\b|\be\b|\bmas\b|\+|\.(?=\s|$))\s*", t) if s and s.strip()]
    pendientes = []  # (cantidad, unidad_escrita, descripcion, problema)
    for seg in segmentos:
        seg = _quitar_relleno(seg.strip())
        cantidad, resto, unidad, problema = _leer_cantidad(seg)
        resto = _quitar_relleno(resto)
        if not resto and cantidad is None:
            continue
        if not tokens_comparacion(resto):
            continue
        pendientes.append((cantidad, unidad, resto, problema))

    if not pendientes:
        res.preguntas.append("No identifiqué ningún material en la solicitud. Indica qué necesitas y en qué cantidad, por ejemplo: «20 gabinetes NEMA 4X».")
    else:
        vectores = indice.codificar_consultas([p[2] for p in pendientes])
        anterior = ""  # sustantivo del renglón anterior, por si el siguiente solo dice «10 de 3/4 pulgada»
        for (cantidad, unidad, desc, problema), vec in zip(pendientes, vectores):
            elegido, candidatos, motivo = _resolver_renglon(conn, indice, desc, usuario_id, vec)
            if motivo in ("ambiguo", "sin_coincidencia") and anterior:
                # Es común escribir «20 tubos PVC 1 pulg, 10 de 2 pulg»: se reintenta con el sustantivo del anterior.
                desc2 = f"{anterior} {desc}"
                elegido2, candidatos2, motivo2 = _resolver_renglon(
                    conn, indice, desc2, usuario_id, indice.codificar_consultas([desc2])[0])
                if motivo2 is None:
                    elegido, candidatos, motivo, desc = elegido2, candidatos2, motivo2, desc2
            palabras = [w for w in re.findall(r"[a-z]+", desc) if len(w) >= 4 and w not in ("pulgada", "pulgadas", "calibre", "polos")]
            anterior = " ".join(palabras[:2]) if palabras else anterior
            rastro = {"texto": desc, "cantidad": cantidad, "unidad_escrita": unidad,
                      "elegido": elegido["ref"] if elegido else None, "motivo": motivo,
                      "candidatos": [c["ref"] for c in candidatos]}
            res.renglones.append(rastro)
            if problema:
                res.preguntas.append(problema)
                continue
            if motivo == "sin_resultados" or motivo == "sin_coincidencia":
                if cantidad is None:
                    res.avisos.append(f"No identifiqué «{desc}» como un material del catálogo; se omitió.")
                else:
                    # Solo se sugiere lo que comparte alguna palabra: «ladrillo» no se parece a un reflector LED.
                    sugerencias = ", ".join(c["concepto"] for c in candidatos[:3] if _se_parece(desc, c))
                    res.preguntas.append(
                        f"No encontré «{desc}» en el catálogo."
                        + (f" ¿Te refieres a: {sugerencias}?" if sugerencias else _lo_que_cubre(conn, usuario_id)))
                continue
            if motivo == "ambiguo":
                opciones = " · ".join(f"{c['concepto']} ({c['codigo']})" for c in candidatos[:4])
                res.preguntas.append(f"«{desc}» puede ser varios artículos: {opciones}. ¿Cuál necesitas?")
                continue
            if cantidad is None:
                res.preguntas.append(f"¿Cuántas unidades ({elegido['unidad'].lower()}) de «{elegido['concepto']}» necesitas?")
                continue
            if unidad and unidad not in UNIDADES_GENERICAS:
                if UNIDAD_CANONICA.get(unidad) != elegido["unidad"]:
                    res.preguntas.append(
                        f"«{elegido['concepto']}» se vende por {elegido['unidad'].lower()}, no por {unidad}. ¿Cuántos {elegido['unidad'].lower()}s necesitas?")
                    continue
            res.lineas.append(Linea(
                tipo="material", codigo=elegido["codigo"], concepto=elegido["concepto"], unidad=elegido["unidad"],
                cantidad=cantidad, costo_unitario_centavos=elegido["precio_centavos"], fuente_ref=elegido["ref"],
                fuente_fecha=elegido["fecha"], antiguedad_meses=elegido["antiguedad_meses"],
            ))
            res.renglones[-1]["categoria"] = elegido["categoria"]

    if pendientes and not res.preguntas and not res.lineas:
        res.preguntas.append("No identifiqué ningún material en la solicitud. Indica qué necesitas y en qué cantidad, por ejemplo: «20 gabinetes NEMA 4X».")

    # Un mismo artículo repetido se suma en un solo renglón.
    unicas: dict[str, Linea] = {}
    for l in res.lineas:
        if l.codigo in unicas:
            previa = unicas[l.codigo]
            unicas[l.codigo] = Linea(**{**previa.__dict__, "cantidad": previa.cantidad + l.cantidad})
            res.avisos.append(f"«{l.concepto}» se pidió más de una vez; se sumaron las cantidades.")
        else:
            unicas[l.codigo] = l
    res.lineas = list(unicas.values())

    por_codigo = {s["codigo"]: s for s in servicios}
    materiales = [l for l in res.lineas if l.tipo == "material"]

    # Instalación
    if info["instalacion"] and materiales:
        categorias = {r["elegido"]: normalizar_texto(r.get("categoria") or "") for r in res.renglones if r.get("elegido")}
        suma: dict[str, int] = {}
        for l in materiales:
            cat = categorias.get(l.fuente_ref, "")
            if info["alcance"] and cat not in info["alcance"]:
                continue
            codigo = INSTALACION_POR_CATEGORIA.get(cat)
            if codigo is None:
                continue
            if codigo == "SRV-INS-CON":
                if l.unidad != "TRAMO":
                    continue  # coples, conectores y abrazaderas no son metros de canalización
                m = re.search(r"x\s*(\d+(?:\.\d+)?)\s*m\b", normalizar_texto(l.concepto))
                if not m:
                    res.avisos.append(f"No se calculó la instalación de «{l.concepto}»: no indica los metros por tramo.")
                    continue
                cantidad = int(round(float(m.group(1)) * l.cantidad))
            else:
                cantidad = l.cantidad
            suma[codigo] = suma.get(codigo, 0) + cantidad
        for codigo, cantidad in suma.items():
            if codigo in por_codigo:
                res.lineas.append(_linea_servicio(por_codigo[codigo], cantidad))
            else:
                res.avisos.append(f"No hay tarifa visible para instalación ({codigo}); no se incluyó.")
        if not suma:
            res.avisos.append("Pediste instalación, pero el tarifario no tiene una tarifa para estos materiales.")

    # Flete
    if info["flete"] and materiales:
        if info["zona"]:
            fletes = [s for s in servicios if s["tipo"] == "Flete" and s["zona"] == info["zona"]]
            if fletes:
                res.lineas.append(_linea_servicio(fletes[0], info["viajes"]))
                if not info["flete_explicito"]:
                    res.avisos.append(f"Se incluyó flete a {info['zona']} porque mencionaste la zona; quítalo si el cliente recoge.")
            else:
                res.avisos.append(f"No hay tarifa de flete visible para {info['zona']}.")
        else:
            res.preguntas.append("¿A qué zona se entregará? Tarifas de flete disponibles: " + ", ".join(sorted(set(z for z in zonas.values()))) + ".")

    # Opcionales: solo premium
    if incluir_opcionales and materiales:
        for s in servicios:
            if s["incluir_en"] == "premium":
                res.lineas.append(_linea_servicio(s, 1))

    return res
