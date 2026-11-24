"""Cotizar a partir de archivos adjuntos (PDF, Excel, CSV, texto de chat) y contexto de fuentes para el modelo de conversación."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.cotizar import cotizar
from agent.llm.adjuntos import leer_adjunto_bytes
from agent.solicitud_archivos import preparar_solicitud

RAIZ = Path(__file__).resolve().parents[2]
VENDEDOR, ADMIN = {"X-Usuario-Id": "u1"}, {"X-Usuario-Id": "u3"}

# Totales con IVA (centavos) por escenario, cotejados contra eval/referencia.py al crear los documentos de prueba.
ESPERADO = {
    "solicitud_01_hotel_costa_dorada.pdf": ("Hotel Costa Dorada", (10710085, 11493834, 13231837)),
    "solicitud_02_constructora_peninsular.xlsx": ("Constructora Peninsular", (1568644, 1683408, 2505559)),
    "solicitud_03_taller_los_pinos.txt": ("Taller Los Pinos", (670952, 720044, 1452317)),
    "solicitud_04_obra_progreso.csv": ("Obra Progreso", (7516239, 8066211, 9484189)),
}


@pytest.fixture(scope="module")
def documentos(tmp_path_factory) -> Path:
    """Los documentos de prueba, generados en una carpeta temporal con el mismo script que usa el equipo."""
    spec = importlib.util.spec_from_file_location("generar_documentos_prueba", RAIZ / "data" / "synthetic" / "generar_documentos_prueba.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    carpeta = tmp_path_factory.mktemp("docs")
    modulo.SALIDA = carpeta
    for f in (modulo.solicitud_hotel, modulo.solicitud_constructora, modulo.solicitud_whatsapp, modulo.solicitud_csv, modulo.lista_proveedor, modulo.politica_interna):
        f()
    return carpeta


def adjunto(carpeta: Path, nombre: str):
    return leer_adjunto_bytes(nombre, (carpeta / nombre).read_bytes())


def totales(r: dict) -> tuple[int, ...]:
    return tuple(r["escenarios"][e]["total_centavos"] for e in ("economico", "recomendado", "premium"))


# --------------------------------------------------------------------------- el normalizador + el intérprete + la calculadora
@pytest.mark.parametrize("nombre", sorted(ESPERADO))
@pytest.mark.parametrize("mensaje", ["", "hazlo con los archivos", "cotiza lo que pide el archivo"])
def test_cada_documento_se_cotiza_completo_y_con_los_totales_esperados(dataset, documentos, nombre, mensaje):
    cliente, esperado = ESPERADO[nombre]
    pedido = preparar_solicitud(mensaje, [adjunto(documentos, nombre)])
    r = cotizar(pedido.texto, "u1", dataset["conn"], dataset["indice"])
    assert (r["estado"], r["preguntas"]) == ("completa", [])
    assert totales(r) == esperado
    assert pedido.cliente == cliente and pedido.renglones >= 2


def test_el_texto_armado_no_tiene_dos_puntos_que_el_interprete_tomaria_como_encabezado(documentos):
    # lo anterior al primer «:» se descarta como encabezado: una línea «Condiciones: …» haría perder renglones sin avisar
    for nombre in ESPERADO:
        assert ":" not in preparar_solicitud("", [adjunto(documentos, nombre)]).texto


def test_el_mensaje_con_cantidades_se_suma_a_lo_del_archivo(dataset, documentos):
    solo = cotizar(preparar_solicitud("", [adjunto(documentos, "solicitud_03_taller_los_pinos.txt")]).texto, "u1", dataset["conn"], dataset["indice"])
    mas = cotizar(preparar_solicitud("y 5 interruptores termomagnéticos 1P 20A", [adjunto(documentos, "solicitud_03_taller_los_pinos.txt")]).texto,
                  "u1", dataset["conn"], dataset["indice"])
    assert totales(mas)[0] > totales(solo)[0]


def test_un_archivo_sin_renglones_con_cantidad_se_avisa_y_no_inventa(documentos):
    vacio = leer_adjunto_bytes("nota.txt", "Buen día, ¿me mandas el catálogo completo cuando puedas?".encode())
    pedido = preparar_solicitud("", [vacio])
    assert pedido.renglones == 0 and any("nota.txt" in a for a in pedido.avisos)


def test_las_imagenes_no_se_leen_aqui(documentos):
    png = leer_adjunto_bytes("foto.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    assert png.tipo == "imagen" and preparar_solicitud("", [png]).renglones == 0


# --------------------------------------------------------------------------- la ruta
@pytest.fixture(scope="module")
def api(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp("api_archivos")
    mp.setenv("TESSERA_DB_PATH", str(carpeta / "api.db"))
    mp.setenv("TESSERA_INDEX_DIR", str(carpeta / "indice"))
    import api.cotizaciones as modulo
    from api.main import app
    from db.database import init_db
    from retrieval.servicio import olvidar_indice

    mp.setattr(modulo, "_proveedor_redaccion", lambda: None)
    olvidar_indice()
    init_db(reset=True)
    with TestClient(app) as cliente:
        yield cliente
    olvidar_indice()
    mp.undo()


def subir(api, documentos, nombres, mensaje="", headers=VENDEDOR):
    archivos = [("archivos", (n, (documentos / n).read_bytes(), "application/octet-stream")) for n in nombres]
    return api.post("/api/cotizaciones/desde-archivos", data={"mensaje": mensaje}, files=archivos, headers=headers)


def test_sin_fuentes_cargadas_dice_que_hay_que_cargarlas(api, documentos):
    r = subir(api, documentos, ["solicitud_02_constructora_peninsular.xlsx"])
    assert r.status_code == 409 and "fuentes" in r.json()["detail"].lower()


def test_la_ruta_crea_la_cotizacion_con_el_cliente_y_los_totales_del_archivo(api, documentos):
    assert api.post("/api/fuentes/cargar-dataset-sintetico", headers=ADMIN).status_code == 200
    r = subir(api, documentos, ["solicitud_02_constructora_peninsular.xlsx"], mensaje="hazlo con el archivo")
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["tipo"] == "cotizacion" and any("solicitud_02_constructora_peninsular.xlsx" in a for a in cuerpo["avisos"])
    c = cuerpo["cotizacion"]
    assert c["cliente"] == "Constructora Peninsular"
    assert tuple(c["escenarios"][e]["totales"]["total_centavos"] for e in ("economico", "recomendado", "premium")) == ESPERADO["solicitud_02_constructora_peninsular.xlsx"][1]


def test_varios_archivos_a_la_vez_se_juntan_en_una_cotizacion(api, documentos):
    r = subir(api, documentos, ["solicitud_03_taller_los_pinos.txt", "solicitud_04_obra_progreso.csv"])
    assert r.status_code == 201
    codigos = {p["codigo"] for p in r.json()["cotizacion"]["escenarios"]["recomendado"]["partidas"]}
    assert {"LAM-REF-50", "VAR-COP-58"} <= codigos


def test_un_archivo_sin_peticion_se_deja_al_chat(api):
    r = api.post("/api/cotizaciones/desde-archivos", data={"mensaje": "¿qué dice?"}, headers=VENDEDOR,
                 files=[("archivos", ("nota.txt", "Hola, buen día".encode(), "text/plain"))])
    assert r.status_code == 200 and r.json()["tipo"] == "conversacion"


def test_una_imagen_se_deja_al_chat(api):
    r = api.post("/api/cotizaciones/desde-archivos", data={"mensaje": "mira"}, headers=VENDEDOR,
                 files=[("archivos", ("foto.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 32, "image/png"))])
    assert r.status_code == 200 and r.json()["tipo"] == "conversacion"


def test_la_ruta_pide_identidad(api, documentos):
    assert subir(api, documentos, ["solicitud_03_taller_los_pinos.txt"], headers={}).status_code == 401


def test_mas_de_cinco_archivos_se_rechazan(api, documentos):
    assert subir(api, documentos, ["solicitud_03_taller_los_pinos.txt"] * 6).status_code == 400


# --------------------------------------------------------------------------- contexto para el modelo de conversación
def test_el_modelo_sabe_que_fuentes_hay_y_como_se_cotiza(dataset):
    from agent.contexto import describir_fuentes

    texto = describir_fuentes(dataset["conn"], "u1")
    assert "catálogo de materiales: 47 artículos" in texto and "No digas que no tienes acceso" in texto


def test_el_contexto_no_cuenta_lo_que_el_usuario_no_puede_abrir(dataset):
    from agent.contexto import describir_fuentes

    conn = dataset["conn"]
    conn.execute("UPDATE fuentes SET permiso = 'Administración' WHERE nombre = 'tarifario_servicios.csv'")
    conn.commit()
    try:
        assert "tarifario" not in describir_fuentes(conn, "u1")
        assert "tarifario" in describir_fuentes(conn, "u3")
    finally:
        conn.execute("UPDATE fuentes SET permiso = 'Comercial' WHERE nombre = 'tarifario_servicios.csv'")
        conn.commit()


def test_sin_fuentes_el_contexto_manda_a_cargarlas(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_DB_PATH", str(tmp_path / "v.db"))
    from agent.contexto import describir_fuentes
    from db.database import get_connection, init_db

    init_db(reset=True)
    conn = get_connection()
    try:
        assert "Aún no hay fuentes cargadas" in describir_fuentes(conn, "u1")
    finally:
        conn.close()


def test_el_chat_agrega_las_fuentes_al_prompt_solo_con_un_usuario_valido(api):
    from api.chat import PROMPT_SISTEMA_COTIZACIONES, _prompt_con_fuentes

    assert _prompt_con_fuentes(None) == PROMPT_SISTEMA_COTIZACIONES
    assert _prompt_con_fuentes("fantasma") == PROMPT_SISTEMA_COTIZACIONES
    assert "Fuentes cargadas que este usuario puede usar" in _prompt_con_fuentes("u1")


# --------------------------------------------------------------------------- lo que pasó al adjuntar documentos que no son solicitudes
def test_una_politica_o_una_lista_de_precios_no_se_toman_como_materiales(documentos):
    # importes como «$150,000.00 MXN» o «15%» eran leídos como cantidades y salía «000.00 debe ser un número entero»
    for nombre in ("fuente_politica_comercial_interna.pdf", "fuente_proveedor_ferreteria_maya.csv"):
        pedido = preparar_solicitud("", [adjunto(documentos, nombre)])
        assert pedido.renglones == 0 and pedido.texto == "" and pedido.cliente is None
        assert "Fuentes" in pedido.avisos[0]
    assert "lista de precios" in preparar_solicitud("", [adjunto(documentos, "fuente_proveedor_ferreteria_maya.csv")]).avisos[0]


def test_mezclar_solicitudes_y_documentos_no_solicitados_cotiza_solo_lo_pedido(dataset, documentos):
    nombres = ["solicitud_02_constructora_peninsular.xlsx", "solicitud_03_taller_los_pinos.txt", "solicitud_04_obra_progreso.csv",
               "fuente_politica_comercial_interna.pdf", "fuente_proveedor_ferreteria_maya.csv"]
    pedido = preparar_solicitud("Necesito que hagas una cotizacion con estos archivos", [adjunto(documentos, n) for n in nombres])
    r = cotizar(pedido.texto, "u1", dataset["conn"], dataset["indice"])
    assert (r["estado"], r["preguntas"]) == ("completa", [])
    assert not [a for a in r["avisos"] if "no identifiqu" in a.lower()]  # nada de «no identifiqué “cliente de crédito…”»
    assert sum("Fuentes" in a for a in pedido.avisos) == 2 and any("clientes distintos" in a for a in pedido.avisos)
    assert pedido.cliente == "Constructora Peninsular"


def test_un_archivo_que_no_aporta_no_pone_su_cliente_ni_sus_servicios(documentos):
    solo = preparar_solicitud("", [adjunto(documentos, "solicitud_03_taller_los_pinos.txt")])
    con = preparar_solicitud("", [adjunto(documentos, "fuente_politica_comercial_interna.pdf"), adjunto(documentos, "solicitud_03_taller_los_pinos.txt")])
    assert (con.texto, con.cliente) == (solo.texto, solo.cliente)


@pytest.mark.parametrize("linea", ["Límite de crédito: $150,000.00 MXN a 15 días", "Hasta 3% sin autorización", "Vigencia 01/11/2026", "pago a 30 días"])
def test_importes_porcentajes_fechas_y_plazos_no_son_renglones(linea):
    assert not preparar_solicitud("", [leer_adjunto_bytes("x.txt", linea.encode())]).renglones


@pytest.mark.parametrize("linea", ["ocupo 3 reflectores LED 50W", "20 gabinetes NEMA 4X", "necesito veinte rollos de cable"])
def test_las_lineas_que_empiezan_con_una_cantidad_si_son_renglones(linea):
    assert preparar_solicitud("", [leer_adjunto_bytes("x.txt", linea.encode())]).renglones == 1


# --------------------------------------------------------------------------- mensajes cortos y material fuera del catálogo
def test_un_mensaje_corto_como_si_no_es_un_error_de_validacion(api):
    r = api.post("/api/cotizaciones", json={"solicitud": "Si"}, headers=VENDEDOR)
    assert r.status_code == 200 and r.json()["tipo"] == "conversacion"


def test_si_nada_se_parece_no_se_sugieren_articulos_sin_relacion_y_se_dice_que_hay(dataset):
    from agent.interpretar import interpretar

    r = interpretar("500 unidades de ladrillo y 50 kilos de cemento", dataset["conn"], dataset["indice"], "u1")
    preguntas = " ".join(r.preguntas)
    assert "No encontré «ladrillo»" in preguntas and "¿Te refieres a" not in preguntas
    assert "El catálogo cargado cubre:" in preguntas and "Gabinetes" in preguntas


def test_si_algo_se_parece_si_se_sugiere(dataset):
    from agent.interpretar import interpretar

    r = interpretar("20 gabinetes de acero inoxidable", dataset["conn"], dataset["indice"], "u1")
    assert any("Gabinete" in q for q in r.preguntas)


def test_el_contexto_da_ejemplos_reales_y_prohibe_inventarlos(dataset):
    from agent.contexto import describir_fuentes

    texto = describir_fuentes(dataset["conn"], "u1")
    assert "Ejemplos reales del catálogo" in texto and "nunca inventes otros" in texto and "«Cable de cobre" in texto
