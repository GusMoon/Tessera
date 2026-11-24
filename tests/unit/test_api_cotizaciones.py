"""API del Hito 3: cotizaciones, estados, permisos por rol, PDF bloqueado sin aprobación, memoria, bitácora y ajustes."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from eval import referencia

RAIZ = Path(__file__).resolve().parents[2]
VENDEDOR, RESPONSABLE, ADMIN = {"X-Usuario-Id": "u1"}, {"X-Usuario-Id": "u2"}, {"X-Usuario-Id": "u3"}
SOLICITUD = "20 gabinetes NEMA 4X intemperie 40x30x20 y 5 interruptores termomagnéticos 1P 20A, con instalación y flete a Umán"


@pytest.fixture(autouse=True)
def sin_llm_real(monkeypatch):
    """Ninguna prueba llama a un LLM real aunque haya claves en .env."""
    import api.cotizaciones as modulo

    monkeypatch.setattr(modulo, "_proveedor_redaccion", lambda: None)


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    carpeta = tmp_path_factory.mktemp("api3")
    mp.setenv("TESSERA_DB_PATH", str(carpeta / "api.db"))
    mp.setenv("TESSERA_INDEX_DIR", str(carpeta / "indice"))
    from api.main import app
    from db.database import init_db
    from retrieval.servicio import olvidar_indice

    olvidar_indice()
    init_db(reset=True)
    with TestClient(app) as cliente:
        assert cliente.post("/api/fuentes/cargar-dataset-sintetico", headers=ADMIN).status_code == 200
        yield cliente
    olvidar_indice()
    mp.undo()


def crear(api, solicitud=SOLICITUD, headers=VENDEDOR, **extra):
    r = api.post("/api/cotizaciones", json={"solicitud": solicitud, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["cotizacion"]


def texto_pdf(contenido: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(contenido)).pages)


# --------------------------------------------------------------------------- identidad
def test_sin_identidad_o_con_un_usuario_inexistente_no_pasa(api):
    assert api.get("/api/cotizaciones").status_code == 401
    r = api.get("/api/cotizaciones", headers={"X-Usuario-Id": "fantasma"})
    assert r.status_code == 401 and "no existe" in r.json()["detail"]


def test_usuarios_para_el_selector_no_pide_identidad(api):
    r = api.get("/api/usuarios")
    assert [u["rol"] for u in r.json()] == ["Vendedor", "Responsable comercial", "Administrador"]


def test_solo_el_administrador_cambia_las_fuentes(api):
    r = api.post("/api/fuentes/limpiar", headers=RESPONSABLE)
    assert r.status_code == 403 and "Administrador" in r.json()["detail"]
    assert api.post("/api/fuentes/subir", files={"file": ("x.csv", b"a", "text/csv")}, headers=VENDEDOR).status_code == 403


# --------------------------------------------------------------------------- crear
def test_crear_guarda_un_borrador_con_tres_escenarios_y_fuentes(api):
    r = api.post("/api/cotizaciones", json={"solicitud": SOLICITUD, "cliente": "Constructora de prueba"}, headers=VENDEDOR)
    assert r.status_code == 201 and r.json()["tipo"] == "cotizacion"
    c = r.json()["cotizacion"]
    assert re.fullmatch(r"#\d{4}", c["folio"]) and c["estado"] == "Borrador" and c["creada_por"] == "Ana Pérez"
    assert c["cliente"] == "Constructora de prueba" and list(c["escenarios"]) == ["economico", "recomendado", "premium"]
    refs = {p["fuente_ref"] for p in c["escenarios"]["recomendado"]["partidas"]}
    assert {"catalogo:GAB-403020", "catalogo:INT-TM-120", "servicio:SRV-INS-GAB", "servicio:SRV-INS-INT", "servicio:SRV-FLE-UMA"} <= refs
    assert all(ref in c["fuentes"] and c["fuentes"][ref]["disponible"] for ref in refs)
    assert c["fuentes"]["catalogo:GAB-403020"]["documento"] == "catalogo_materiales.csv"
    assert c["historial"][0]["texto"].startswith("Borrador creado con 3 escenarios")
    assert c["parecidas"] and all(h["ref"].startswith("historial:") for h in c["parecidas"])


def test_los_totales_del_servidor_coinciden_con_la_referencia_independiente(api):
    c = crear(api, "20 gabinetes NEMA 4X intemperie 40x30x20")
    esperado = referencia.totales_esperados([{"sku": "GAB-403020", "cantidad": 20}], [])
    for esc, e in esperado.items():
        t = c["escenarios"][esc]["totales"]
        assert (t["subtotal_centavos"], t["iva_centavos"], t["total_centavos"]) == (e["subtotal_centavos"], e["iva_centavos"], e["total_centavos"])


def test_si_falta_un_dato_se_pregunta_y_no_se_guarda(api):
    antes = len(api.get("/api/cotizaciones", headers=VENDEDOR).json())
    r = api.post("/api/cotizaciones", json={"solicitud": "10 cables calibre 12"}, headers=VENDEDOR)
    assert r.status_code == 200 and r.json()["tipo"] == "aclaracion" and "CAB-THW-12N" in r.json()["preguntas"][0]
    assert len(api.get("/api/cotizaciones", headers=VENDEDOR).json()) == antes


def test_una_pregunta_general_se_deja_al_chat(api):
    r = api.post("/api/cotizaciones", json={"solicitud": "¿Cuánto cobramos de flete a Progreso la última vez?"}, headers=VENDEDOR)
    assert r.status_code == 200 and r.json() == {"tipo": "conversacion"}


def test_sin_fuentes_cargadas_no_se_cotiza(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSERA_DB_PATH", str(tmp_path / "vacia.db"))
    from api.main import app
    from db.database import init_db

    init_db(reset=True)
    r = TestClient(app).post("/api/cotizaciones", json={"solicitud": "20 gabinetes"}, headers=VENDEDOR)
    assert r.status_code == 409 and "Fuentes" in r.json()["detail"]


def test_la_solicitud_se_valida(api):
    assert api.post("/api/cotizaciones", json={"solicitud": ""}, headers=VENDEDOR).status_code == 422
    assert api.post("/api/cotizaciones", json={"solicitud": "x" * 4001}, headers=VENDEDOR).status_code == 422


def test_crear_queda_en_la_bitacora_con_el_folio(api):
    c = crear(api)
    filas = api.get("/api/bitacora", headers=VENDEDOR).json()
    fila = next(f for f in filas if f["cotizacion"] == c["folio"])
    assert fila["usuario"] == "Ana Pérez" and "calcular_cotizacion" in fila["herramientas"] and "catalogo:GAB-403020" in fila["documentos"]


def test_listar_y_detalle(api):
    c = crear(api)
    assert c["id"] in [x["id"] for x in api.get("/api/cotizaciones", headers=RESPONSABLE).json()]
    assert api.get(f"/api/cotizaciones/{c['id']}", headers=RESPONSABLE).json()["folio"] == c["folio"]
    assert api.get("/api/cotizaciones/99999", headers=VENDEDOR).status_code == 404


# --------------------------------------------------------------------------- editar
def test_editar_cantidad_recalcula_en_el_servidor_y_marca_la_partida(api):
    c = crear(api)
    p = next(x for x in c["escenarios"]["recomendado"]["partidas"] if x["codigo"] == "GAB-403020")
    r = api.patch(f"/api/cotizaciones/{c['id']}/partidas/{p['id']}", json={"cantidad": 25}, headers=VENDEDOR)
    assert r.status_code == 200
    nueva = r.json()
    editada = next(x for x in nueva["escenarios"]["recomendado"]["partidas"] if x["id"] == p["id"])
    assert editada["cantidad"] == 25 and editada["editada_por"] == "Ana Pérez" and editada["importe_centavos"] == 25 * p["precio_unitario_centavos"]
    assert nueva["escenarios"]["recomendado"]["totales"]["subtotal_centavos"] > c["escenarios"]["recomendado"]["totales"]["subtotal_centavos"]
    assert nueva["escenarios"]["economico"]["totales"] == c["escenarios"]["economico"]["totales"]  # solo cambia ese escenario
    assert "cantidad 20 → 25" in nueva["historial"][-1]["texto"]


def test_editar_precio(api):
    c = crear(api)
    p = c["escenarios"]["premium"]["partidas"][0]
    r = api.patch(f"/api/cotizaciones/{c['id']}/partidas/{p['id']}", json={"precio_unitario_centavos": 123456}, headers=VENDEDOR).json()
    assert r["escenarios"]["premium"]["partidas"][0]["precio_unitario_centavos"] == 123456
    assert "$1,234.56 MXN" in r["historial"][-1]["texto"]


@pytest.mark.parametrize("cuerpo", [{}, {"cantidad": 0}, {"cantidad": -2}, {"cantidad": 1.5}, {"cantidad": "5"}, {"precio_unitario_centavos": -1}, {"precio_unitario_centavos": 10.5}])
def test_ediciones_invalidas_se_rechazan(api, cuerpo):
    c = crear(api)
    pid = c["escenarios"]["recomendado"]["partidas"][0]["id"]
    assert api.patch(f"/api/cotizaciones/{c['id']}/partidas/{pid}", json=cuerpo, headers=VENDEDOR).status_code == 422


def test_no_se_edita_una_partida_ajena_ni_inexistente(api):
    a, b = crear(api), crear(api)
    pid_b = b["escenarios"]["recomendado"]["partidas"][0]["id"]
    assert api.patch(f"/api/cotizaciones/{a['id']}/partidas/{pid_b}", json={"cantidad": 3}, headers=VENDEDOR).status_code == 404
    assert api.patch(f"/api/cotizaciones/{a['id']}/partidas/999999", json={"cantidad": 3}, headers=VENDEDOR).status_code == 404


def test_editar_notas(api):
    c = crear(api)
    r = api.patch(f"/api/cotizaciones/{c['id']}/escenarios/premium", json={"notas": "Cliente pide entrega en la mañana."}, headers=VENDEDOR).json()
    assert r["escenarios"]["premium"]["notas"] == "Cliente pide entrega en la mañana." and "notas del agente (Premium)" in r["historial"][-1]["texto"]
    assert api.patch(f"/api/cotizaciones/{c['id']}/escenarios/lujo", json={"notas": "x"}, headers=VENDEDOR).status_code == 422


# --------------------------------------------------------------------------- estados y aprobación
def test_enviar_a_revision_solo_desde_borrador(api):
    c = crear(api)
    assert api.post(f"/api/cotizaciones/{c['id']}/enviar", headers=VENDEDOR).json()["estado"] == "En revisión"
    assert api.post(f"/api/cotizaciones/{c['id']}/enviar", headers=VENDEDOR).status_code == 409


def test_un_vendedor_no_puede_aprobar_ni_rechazar(api):
    c = crear(api)
    r = api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "recomendado"}, headers=VENDEDOR)
    assert r.status_code == 403 and "Vendedor" in r.json()["detail"]
    assert api.post(f"/api/cotizaciones/{c['id']}/rechazar", json={"motivo": "x"}, headers=VENDEDOR).status_code == 403
    assert api.get(f"/api/cotizaciones/{c['id']}", headers=VENDEDOR).json()["estado"] == "Borrador"


def test_aprobar_registra_quien_cuando_y_cuanto_y_bloquea_la_edicion(api):
    c = crear(api)
    api.post(f"/api/cotizaciones/{c['id']}/enviar", headers=VENDEDOR)
    r = api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "recomendado"}, headers=RESPONSABLE)
    assert r.status_code == 200
    a = r.json()
    assert a["estado"] == "Aprobada" and a["escenario_aprobado"] == "recomendado" and a["aprobada_por"] == "Marcos Díaz" and a["fecha_aprobacion"]
    assert a["historial"][-1]["texto"] == "Aprobó el escenario Recomendado."
    pid = a["escenarios"]["recomendado"]["partidas"][0]["id"]
    assert api.patch(f"/api/cotizaciones/{c['id']}/partidas/{pid}", json={"cantidad": 99}, headers=VENDEDOR).status_code == 409
    assert api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "premium"}, headers=RESPONSABLE).status_code == 409
    assert api.post(f"/api/cotizaciones/{c['id']}/rechazar", json={}, headers=RESPONSABLE).status_code == 409
    fila = next(f for f in api.get("/api/bitacora", headers=RESPONSABLE).json() if f["pregunta"].startswith("Aprobación") and f["cotizacion"] == c["folio"])
    assert fila["aprobado_por"] == "Marcos Díaz"


def test_aprobar_valida_el_escenario(api):
    c = crear(api)
    assert api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "dorado"}, headers=RESPONSABLE).status_code == 422


def test_rechazar_guarda_el_motivo_y_no_da_pdf(api):
    c = crear(api)
    r = api.post(f"/api/cotizaciones/{c['id']}/rechazar", json={"motivo": "Precio base desactualizado."}, headers=RESPONSABLE).json()
    assert r["estado"] == "Rechazada" and r["motivo_rechazo"] == "Precio base desactualizado."
    assert api.get(f"/api/cotizaciones/{c['id']}/pdf", headers=RESPONSABLE).status_code == 409


# --------------------------------------------------------------------------- regla 3: PDF solo con aprobación
def test_sin_aprobacion_el_pdf_responde_409_y_no_genera_nada(api):
    c = crear(api)
    for h in (VENDEDOR, RESPONSABLE, ADMIN):
        r = api.get(f"/api/cotizaciones/{c['id']}/pdf", headers=h)
        assert r.status_code == 409 and "aprobación" in r.json()["detail"] and r.headers["content-type"].startswith("application/json")


def test_con_aprobacion_el_pdf_cita_las_fuentes_y_al_aprobador(api):
    c = crear(api, cliente="Hotel Prueba")
    api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "premium"}, headers=RESPONSABLE)
    r = api.get(f"/api/cotizaciones/{c['id']}/pdf", headers=VENDEDOR)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert f"Cotizacion-{c['folio'].lstrip('#')}.pdf" in r.headers["content-disposition"]
    texto = texto_pdf(r.content)
    detalle = api.get(f"/api/cotizaciones/{c['id']}", headers=VENDEDOR).json()
    total = detalle["escenarios"]["premium"]["totales"]["total_centavos"]
    for esperado in (c["folio"], "Hotel Prueba", "Premium", "Aprobada por Marcos Díaz", f"${total / 100:,.2f}", "catalogo:GAB-403020",
                     "servicio:SRV-OPC-GAR", "catalogo_materiales.csv", "ningún modelo de IA calculó"):
        assert esperado in re.sub(r"\s+", " ", texto) or esperado in texto, esperado


def test_el_pdf_marca_los_precios_de_mas_de_seis_meses(api):
    c = crear(api, "5 interruptores termomagnéticos 1P 20A")  # el precio del catálogo tiene 8 meses
    api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "recomendado"}, headers=RESPONSABLE)
    assert "(!) precio de" in texto_pdf(api.get(f"/api/cotizaciones/{c['id']}/pdf", headers=VENDEDOR).content)


def test_el_pdf_se_genera_con_el_estado_y_la_aprobacion_de_la_base(api):
    """La puerta es `generar_pdf`: sin fila en `aprobaciones` falla aunque el estado diga «Aprobada»."""
    from db.database import get_connection
    from documents.pdf import AprobacionRequerida, IntegridadError, generar_pdf

    c = crear(api)
    conn = get_connection()
    try:
        conn.execute("UPDATE cotizaciones SET estado = 'Aprobada', escenario_aprobado = 'recomendado' WHERE id = ?", (c["id"],))
        conn.commit()
        with pytest.raises(AprobacionRequerida):
            generar_pdf(conn, int(c["id"]))  # estado manipulado sin aprobación registrada
        conn.execute("UPDATE cotizaciones SET estado = 'Borrador' WHERE id = ?", (c["id"],))
        conn.commit()
        api.post(f"/api/cotizaciones/{c['id']}/aprobar", json={"escenario": "recomendado"}, headers=RESPONSABLE)
        assert generar_pdf(conn, int(c["id"])).startswith(b"%PDF")
        conn.execute("UPDATE cotizacion_partidas SET cantidad = cantidad + 1 WHERE cotizacion_id = ? AND escenario = 'recomendado'", (c["id"],))
        conn.commit()
        with pytest.raises(IntegridadError):
            generar_pdf(conn, int(c["id"]))  # algo cambió después de aprobar
        assert api.get(f"/api/cotizaciones/{c['id']}/pdf", headers=VENDEDOR).status_code == 409
    finally:
        conn.close()


def test_no_hay_otra_ruta_de_codigo_que_dibuje_el_pdf():
    """Regla 3 en código: `_dibujar` solo se llama desde `generar_pdf`, y nadie más importa ni usa ReportLab."""
    fuente = (RAIZ / "documents" / "pdf.py").read_text(encoding="utf-8")
    assert len(re.findall(r"\b_dibujar\(", fuente)) == 2  # la definición y la llamada dentro de generar_pdf
    assert fuente.index("def generar_pdf") < fuente.index("return _dibujar(")
    for ruta in RAIZ.rglob("*.py"):
        partes = set(ruta.relative_to(RAIZ).parts)
        if partes & {".venv", "node_modules", "tests"} or ruta.name in ("pdf.py", "generar_datos.py", "generar_documentos_prueba.py"):  # los generadores dibujan fichas y solicitudes sintéticas, no cotizaciones
            continue
        codigo = ruta.read_text(encoding="utf-8", errors="ignore")
        assert "_dibujar" not in codigo and "reportlab" not in codigo, f"{ruta} toca el PDF fuera de documents/pdf.py"


def test_las_fuentes_restringidas_no_muestran_su_extracto(api):
    from db.database import get_connection

    c = crear(api)
    conn = get_connection()
    try:
        conn.execute("UPDATE fragmentos SET permiso = 'Administración' WHERE ref = 'catalogo:GAB-403020'")
        conn.commit()
        v = api.get(f"/api/cotizaciones/{c['id']}", headers=VENDEDOR).json()["fuentes"]["catalogo:GAB-403020"]
        a = api.get(f"/api/cotizaciones/{c['id']}", headers=ADMIN).json()["fuentes"]["catalogo:GAB-403020"]
        assert v["restringido"] and v["extracto"] is None and not a["restringido"] and a["extracto"]
    finally:
        conn.execute("UPDATE fragmentos SET permiso = 'Todos' WHERE ref = 'catalogo:GAB-403020'")
        conn.commit()
        conn.close()


# --------------------------------------------------------------------------- memoria
def test_memoria_un_vendedor_propone_y_quien_aprueba_confirma(api):
    r = api.post("/api/memoria", json={"texto": "El cliente X paga a 30 días."}, headers=VENDEDOR)
    assert r.status_code == 201
    h = r.json()
    assert h["por_confirmar"] is True and h["estado"] == "Activa" and h["origen"] == "Propuesto por Ana Pérez"
    assert api.post(f"/api/memoria/{h['id']}/confirmar", headers=VENDEDOR).status_code == 403
    assert api.patch(f"/api/memoria/{h['id']}", json={"estado": "Pausada"}, headers=VENDEDOR).status_code == 403
    assert api.delete(f"/api/memoria/{h['id']}", headers=VENDEDOR).status_code == 403
    assert api.post(f"/api/memoria/{h['id']}/confirmar", headers=RESPONSABLE).json()["por_confirmar"] is False
    editado = api.patch(f"/api/memoria/{h['id']}", json={"texto": "El cliente X paga a 45 días."}, headers=RESPONSABLE).json()
    assert editado["texto"].endswith("45 días.") and editado["por_confirmar"] is True  # lo editado se vuelve a validar
    assert api.patch(f"/api/memoria/{h['id']}", json={"estado": "Pausada"}, headers=RESPONSABLE).json()["estado"] == "Pausada"
    assert api.delete(f"/api/memoria/{h['id']}", headers=RESPONSABLE).status_code == 204
    assert h["id"] not in [x["id"] for x in api.get("/api/memoria", headers=VENDEDOR).json()]


def test_memoria_errores(api):
    assert api.post("/api/memoria", json={"texto": ""}, headers=VENDEDOR).status_code == 422
    assert api.post("/api/memoria/99999/confirmar", headers=RESPONSABLE).status_code == 404
    assert api.patch("/api/memoria/99999", json={"texto": "x"}, headers=RESPONSABLE).status_code == 404
    assert api.patch("/api/memoria/1", json={}, headers=RESPONSABLE).status_code == 422


# --------------------------------------------------------------------------- bitácora y ajustes
def test_un_vendedor_solo_ve_su_bitacora(api):
    crear(api, headers=VENDEDOR)
    crear(api, headers=RESPONSABLE)
    propias = api.get("/api/bitacora", headers=VENDEDOR).json()
    todas = api.get("/api/bitacora", headers=RESPONSABLE).json()
    assert propias and {f["usuario"] for f in propias} == {"Ana Pérez"}
    assert {"Ana Pérez", "Marcos Díaz"} <= {f["usuario"] for f in todas}


def test_ajustes_solo_lectura(api):
    crear(api)
    a = api.get("/api/ajustes", headers=VENDEDOR).json()
    assert a["fragmentos_indexados"] > 100 and a["ultima_cotizacion_ms"]["total"] >= 0 and a["embedder"] == "hash"
    assert api.post("/api/ajustes", headers=ADMIN).status_code == 405


def test_borrar_datos_es_cosa_del_administrador_y_conserva_las_fuentes(api):
    crear(api)
    assert api.delete("/api/datos", headers=RESPONSABLE).status_code == 403
    r = api.delete("/api/datos", headers=ADMIN)
    assert r.status_code == 200 and r.json()["borrado"]["cotizaciones"] >= 1
    assert api.get("/api/cotizaciones", headers=ADMIN).json() == [] and api.get("/api/memoria", headers=ADMIN).json() == []
    assert len(api.get("/api/fuentes").json()) == 13  # las fuentes cargadas siguen ahí
    assert len(api.get("/api/usuarios").json()) == 3
    assert crear(api)["folio"]  # y se puede volver a cotizar


def test_la_conexion_de_cada_peticion_se_puede_cerrar_desde_otro_hilo():
    """Regresión: FastAPI abre y cierra la dependencia en hilos distintos; SQLite lo rechazaba y la API respondía 500."""
    import threading

    from api.deps import conexion

    gen = conexion()
    next(gen)
    errores: list[Exception] = []

    def cerrar():
        try:
            gen.close()
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    hilo = threading.Thread(target=cerrar)
    hilo.start()
    hilo.join()
    assert errores == []
