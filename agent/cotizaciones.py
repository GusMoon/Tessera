"""Cotizaciones guardadas: crear desde el resultado de `cotizar`, leer, editar, aprobar y rechazar.

Todo importe se guarda en centavos enteros y cada partida conserva su propia copia de la fuente (regla 2): si el
catálogo cambia después, la cotización no cambia sola. Los totales siempre salen de `agent.tools.calcular_cotizacion`
(regla 1). La aprobación queda en `aprobaciones`; sin esa fila no existe ruta que genere el PDF (regla 3).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from agent.tools.calcular_cotizacion import ESCENARIOS, totales
from retrieval.permisos import permisos_de

ETIQUETAS = {"economico": "Económico", "recomendado": "Recomendado", "premium": "Premium"}
ESTADOS_EDITABLES = ("Borrador", "En revisión")
AGENTE = "Tessera (agente)"


class ErrorCotizacion(Exception):
    estado_http = 400


class NoEncontrada(ErrorCotizacion):
    estado_http = 404


class EstadoNoPermitido(ErrorCotizacion):
    estado_http = 409


class DatoInvalido(ErrorCotizacion):
    estado_http = 422


def _ahora() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def pesos(centavos: int) -> str:
    return f"${centavos / 100:,.2f} MXN"


def _folio(cot_id: int) -> str:
    return f"#{cot_id:04d}"


def _historial(conn: sqlite3.Connection, cot_id: int, usuario: str, texto: str) -> None:
    conn.execute("INSERT INTO cotizacion_historial (cotizacion_id, fecha, usuario, texto) VALUES (?, ?, ?, ?)", (cot_id, _ahora(), usuario, texto))


# --------------------------------------------------------------------------- crear
def crear(conn: sqlite3.Connection, resultado: dict, usuario_id: str, solicitud: str, cliente: str | None = None) -> int:
    """Guarda un resultado `completa` de `cotizar`/`orquestar` como borrador. Devuelve el id."""
    if resultado.get("estado") != "completa" or not resultado.get("escenarios"):
        raise DatoInvalido("Solo se puede guardar una cotización completa; faltan datos por aclarar.")
    redaccion = resultado.get("redaccion") or {}
    textos = redaccion.get("escenarios") or {}
    cur = conn.execute(
        "INSERT INTO cotizaciones (folio, cliente, solicitud, estado, creada_por, fecha, contexto_json) VALUES (?, ?, ?, 'Borrador', ?, ?, ?)",
        (f"tmp-{datetime.now().timestamp()}", (cliente or resultado.get("cliente") or "Cliente por definir").strip(), solicitud, usuario_id, _ahora(),
         json.dumps({
             "avisos": resultado.get("avisos", []),
             "parecidas": [{"ref": h["ref"], "folio": h["folio"], "cliente": h["cliente"], "fecha": h["fecha"]} for h in resultado.get("historial_parecido", [])],
             "redaccion": {"origen": redaccion.get("origen"), "modelo": redaccion.get("modelo")},
         }, ensure_ascii=False)),
    )
    cot_id = int(cur.lastrowid)
    conn.execute("UPDATE cotizaciones SET folio = ? WHERE id = ?", (_folio(cot_id), cot_id))
    for esc in ESCENARIOS:
        e = resultado["escenarios"][esc]
        texto = textos.get(esc) or {}
        # El riesgo por precios viejos lo calcula la interfaz a partir de las fechas: no se duplica aquí.
        riesgos = [] if redaccion.get("origen") == "determinista" else texto.get("riesgos", [])
        conn.execute(
            "INSERT INTO cotizacion_escenarios (cotizacion_id, escenario, margen_puntos_base, notas, riesgos_json) VALUES (?, ?, ?, ?, ?)",
            (cot_id, esc, e["margen_objetivo_puntos_base"], texto.get("notas", ""), json.dumps(riesgos, ensure_ascii=False)),
        )
        for p in e["partidas"]:
            conn.execute(
                """INSERT INTO cotizacion_partidas (cotizacion_id, escenario, orden, tipo, codigo, concepto, unidad, cantidad,
                       costo_unitario_centavos, precio_unitario_centavos, fuente_ref, fuente_fecha, antiguedad_meses, precio_antiguo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cot_id, esc, p["orden"], p["tipo"], p["codigo"], p["concepto"], p["unidad"], p["cantidad"], p["costo_unitario_centavos"],
                 p["precio_unitario_centavos"], p["fuente_ref"], p["fuente_fecha"], p["antiguedad_meses"], int(p["precio_antiguo"])),
            )
    n_fuentes = len({p["fuente_ref"] for p in resultado["escenarios"]["recomendado"]["partidas"]})
    _historial(conn, cot_id, AGENTE, f"Borrador creado con 3 escenarios a partir de {n_fuentes} fuentes.")
    conn.commit()
    return cot_id


# --------------------------------------------------------------------------- leer
def _fuente(conn: sqlite3.Connection, ref: str, permisos: frozenset[str]) -> dict:
    tipo, _, codigo = ref.partition(":")
    f = conn.execute(
        """SELECT g.titulo, g.texto, g.fecha, g.permiso, g.fuente_id, u.nombre AS documento
           FROM fragmentos g JOIN fuentes u ON u.id = g.fuente_id WHERE g.ref = ? LIMIT 1""",
        (ref,),
    ).fetchone()
    lugar = {"catalogo": "Catálogo", "servicio": "Tarifario de servicios", "historial": "Cotización histórica", "ficha": "Ficha técnica"}.get(tipo, tipo)
    if f is None:
        return {"ref": ref, "etiqueta": codigo or ref, "fecha": None, "ubicacion": lugar, "extracto": None, "fuente_id": None,
                "documento": None, "permiso": None, "restringido": False, "disponible": False}
    restringido = f["permiso"] not in permisos
    return {
        "ref": ref, "etiqueta": codigo, "fecha": f["fecha"], "ubicacion": f"{lugar} · {f['documento']}",
        "extracto": None if restringido else f["texto"][:400], "fuente_id": f["fuente_id"], "documento": f["documento"],
        "permiso": f["permiso"], "restringido": restringido, "disponible": True,
    }


def _escenario(conn: sqlite3.Connection, cot_id: int, esc: str, fila: sqlite3.Row) -> dict:
    partidas = [
        {
            "id": str(p["id"]), "tipo": p["tipo"], "codigo": p["codigo"], "concepto": p["concepto"], "unidad": p["unidad"],
            "cantidad": p["cantidad"], "costo_unitario_centavos": p["costo_unitario_centavos"],
            "precio_unitario_centavos": p["precio_unitario_centavos"], "importe_centavos": p["cantidad"] * p["precio_unitario_centavos"],
            "fuente_ref": p["fuente_ref"], "fuente_fecha": p["fuente_fecha"], "antiguedad_meses": p["antiguedad_meses"],
            "precio_antiguo": bool(p["precio_antiguo"]), "editada_por": p["editada_por"],
        }
        for p in conn.execute("SELECT * FROM cotizacion_partidas WHERE cotizacion_id = ? AND escenario = ? ORDER BY orden, id", (cot_id, esc))
    ]
    return {
        "notas": fila["notas"], "riesgos": json.loads(fila["riesgos_json"]), "margen_objetivo_puntos_base": fila["margen_puntos_base"],
        "partidas": partidas,
        "totales": totales([p["importe_centavos"] for p in partidas], [p["cantidad"] * p["costo_unitario_centavos"] for p in partidas]),
    }


def obtener(conn: sqlite3.Connection, cot_id: int, usuario_id: str) -> dict:
    c = conn.execute(
        """SELECT c.*, u.nombre AS creador, a.aprobado_por, a.fecha AS fecha_aprobacion, ua.nombre AS nombre_aprobador
           FROM cotizaciones c JOIN usuarios u ON u.id = c.creada_por
           LEFT JOIN aprobaciones a ON a.cotizacion_id = c.id LEFT JOIN usuarios ua ON ua.id = a.aprobado_por WHERE c.id = ?""",
        (cot_id,),
    ).fetchone()
    if c is None:
        raise NoEncontrada(f"No existe la cotización {cot_id}.")
    escenarios = {r["escenario"]: _escenario(conn, cot_id, r["escenario"], r)
                  for r in conn.execute("SELECT * FROM cotizacion_escenarios WHERE cotizacion_id = ?", (cot_id,))}
    permisos = permisos_de(usuario_id, conn)
    refs = {p["fuente_ref"] for e in escenarios.values() for p in e["partidas"]}
    contexto = json.loads(c["contexto_json"] or "{}")
    refs |= {h["ref"] for h in contexto.get("parecidas", [])}
    return {
        "id": str(c["id"]), "folio": c["folio"], "cliente": c["cliente"], "solicitud": c["solicitud"], "fecha": c["fecha"][:10],
        "estado": c["estado"], "creada_por": c["creador"], "escenario_aprobado": c["escenario_aprobado"], "motivo_rechazo": c["motivo_rechazo"],
        "aprobada_por": c["nombre_aprobador"], "fecha_aprobacion": c["fecha_aprobacion"],
        "escenarios": {esc: escenarios[esc] for esc in ESCENARIOS if esc in escenarios},
        "historial": [dict(h) for h in conn.execute(
            "SELECT fecha, usuario, texto FROM cotizacion_historial WHERE cotizacion_id = ? ORDER BY id", (cot_id,))],
        "avisos": contexto.get("avisos", []), "parecidas": contexto.get("parecidas", []), "redaccion": contexto.get("redaccion", {}),
        "fuentes": {ref: _fuente(conn, ref, permisos) for ref in sorted(refs)},
    }


def listar(conn: sqlite3.Connection, usuario_id: str) -> list[dict]:
    return [obtener(conn, f["id"], usuario_id) for f in conn.execute("SELECT id FROM cotizaciones ORDER BY id DESC")]


# --------------------------------------------------------------------------- editar
def _estado(conn: sqlite3.Connection, cot_id: int) -> str:
    f = conn.execute("SELECT estado FROM cotizaciones WHERE id = ?", (cot_id,)).fetchone()
    if f is None:
        raise NoEncontrada(f"No existe la cotización {cot_id}.")
    return f["estado"]


def _exigir_editable(conn: sqlite3.Connection, cot_id: int) -> None:
    estado = _estado(conn, cot_id)
    if estado not in ESTADOS_EDITABLES:
        raise EstadoNoPermitido(f"La cotización está {estado.lower()} y ya no se puede editar.")


def editar_partida(conn: sqlite3.Connection, cot_id: int, partida_id: int, usuario: dict, cantidad: int | None, precio_unitario_centavos: int | None) -> None:
    _exigir_editable(conn, cot_id)
    p = conn.execute("SELECT * FROM cotizacion_partidas WHERE id = ? AND cotizacion_id = ?", (partida_id, cot_id)).fetchone()
    if p is None:
        raise NoEncontrada("No existe esa partida en la cotización.")
    if cantidad is None and precio_unitario_centavos is None:
        raise DatoInvalido("Indica la cantidad o el precio unitario nuevo.")
    if cantidad is not None and (isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1):
        raise DatoInvalido("La cantidad debe ser un entero mayor o igual a 1.")
    if precio_unitario_centavos is not None and (isinstance(precio_unitario_centavos, bool) or not isinstance(precio_unitario_centavos, int) or precio_unitario_centavos < 0):
        raise DatoInvalido("El precio unitario debe ser un entero de centavos mayor o igual a 0.")
    cambios = []
    if cantidad is not None and cantidad != p["cantidad"]:
        cambios.append(f"cantidad {p['cantidad']} → {cantidad}")
    if precio_unitario_centavos is not None and precio_unitario_centavos != p["precio_unitario_centavos"]:
        cambios.append(f"precio {pesos(p['precio_unitario_centavos'])} → {pesos(precio_unitario_centavos)}")
    if not cambios:
        return
    conn.execute(
        "UPDATE cotizacion_partidas SET cantidad = ?, precio_unitario_centavos = ?, editada_por = ? WHERE id = ?",
        (cantidad if cantidad is not None else p["cantidad"],
         precio_unitario_centavos if precio_unitario_centavos is not None else p["precio_unitario_centavos"], usuario["nombre"], partida_id),
    )
    _historial(conn, cot_id, usuario["nombre"], f"Editó «{p['concepto']}» ({ETIQUETAS[p['escenario']]}): {', '.join(cambios)}.")
    conn.commit()


def editar_notas(conn: sqlite3.Connection, cot_id: int, escenario: str, notas: str, usuario: dict) -> None:
    _exigir_editable(conn, cot_id)
    f = conn.execute("SELECT notas FROM cotizacion_escenarios WHERE cotizacion_id = ? AND escenario = ?", (cot_id, escenario)).fetchone()
    if f is None:
        raise NoEncontrada("No existe ese escenario.")
    if f["notas"] == notas:
        return
    conn.execute("UPDATE cotizacion_escenarios SET notas = ? WHERE cotizacion_id = ? AND escenario = ?", (notas, cot_id, escenario))
    _historial(conn, cot_id, usuario["nombre"], f"Editó las notas del agente ({ETIQUETAS[escenario]}).")
    conn.commit()


# --------------------------------------------------------------------------- estados
def enviar_a_revision(conn: sqlite3.Connection, cot_id: int, usuario: dict) -> None:
    estado = _estado(conn, cot_id)
    if estado != "Borrador":
        raise EstadoNoPermitido(f"Solo un borrador se puede enviar a revisión; esta cotización está {estado.lower()}.")
    conn.execute("UPDATE cotizaciones SET estado = 'En revisión' WHERE id = ?", (cot_id,))
    _historial(conn, cot_id, usuario["nombre"], "Enviada a revisión.")
    conn.commit()


def aprobar(conn: sqlite3.Connection, cot_id: int, escenario: str, usuario: dict) -> int:
    """Registra la aprobación (regla 3) y devuelve el total aprobado en centavos."""
    _exigir_editable(conn, cot_id)
    if escenario not in ESCENARIOS:
        raise DatoInvalido(f"Escenario no válido: {escenario!r}. Valores: {', '.join(ESCENARIOS)}.")
    partidas = conn.execute(
        "SELECT cantidad, precio_unitario_centavos, costo_unitario_centavos FROM cotizacion_partidas WHERE cotizacion_id = ? AND escenario = ?",
        (cot_id, escenario),
    ).fetchall()
    if not partidas:
        raise DatoInvalido("El escenario no tiene partidas.")
    total = totales([p["cantidad"] * p["precio_unitario_centavos"] for p in partidas],
                    [p["cantidad"] * p["costo_unitario_centavos"] for p in partidas])["total_centavos"]
    ahora = _ahora()
    conn.execute(
        "INSERT INTO aprobaciones (cotizacion_id, escenario, aprobado_por, fecha, total_centavos) VALUES (?, ?, ?, ?, ?)",
        (cot_id, escenario, usuario["id"], ahora, total),
    )
    conn.execute("UPDATE cotizaciones SET estado = 'Aprobada', escenario_aprobado = ? WHERE id = ?", (escenario, cot_id))
    _historial(conn, cot_id, usuario["nombre"], f"Aprobó el escenario {ETIQUETAS[escenario]}.")
    conn.commit()
    return total


def rechazar(conn: sqlite3.Connection, cot_id: int, motivo: str, usuario: dict) -> None:
    _exigir_editable(conn, cot_id)
    motivo = motivo.strip() or "Sin motivo indicado."
    conn.execute("UPDATE cotizaciones SET estado = 'Rechazada', motivo_rechazo = ? WHERE id = ?", (motivo, cot_id))
    _historial(conn, cot_id, usuario["nombre"], f"Rechazó la cotización: {motivo}")
    conn.commit()

