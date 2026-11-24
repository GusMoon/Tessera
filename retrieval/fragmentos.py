"""Parte lo cargado en SQLite en fragmentos citables e indexables (catálogo, historial, servicios, fichas).

Cada fragmento tiene una `ref` estable (p. ej. `catalogo:GAB-403020`) que es la fuente que se cita en las
cotizaciones (regla 2), hereda el `permiso` de su fuente (regla 6) y lleva la fecha del dato citado.
"""

from __future__ import annotations

import re
import sqlite3

TAM_TROZO_FICHA = 800


def _trozos(texto: str, tam: int = TAM_TROZO_FICHA) -> list[str]:
    """Parte un texto largo en trozos de ~`tam` caracteres, cortando en saltos de línea cuando se puede."""
    limpio = re.sub(r"[ \t]+", " ", texto).strip()
    if len(limpio) <= tam:
        return [limpio] if limpio else []
    trozos, actual = [], ""
    for linea in limpio.splitlines():
        if actual and len(actual) + len(linea) + 1 > tam:
            trozos.append(actual.strip())
            actual = ""
        actual += linea + "\n"
    if actual.strip():
        trozos.append(actual.strip())
    return trozos


def construir_fragmentos(conn: sqlite3.Connection) -> int:
    """Vacía y vuelve a llenar `fragmentos` y `fragmentos_fts`. Devuelve cuántos fragmentos quedaron."""
    conn.execute("DELETE FROM fragmentos_fts")
    conn.execute("DELETE FROM fragmentos")
    filas: list[tuple] = []  # (fuente_id, tipo, ref, titulo, texto, permiso, fecha)

    for r in conn.execute(
        """SELECT c.sku, c.descripcion, c.categoria, c.unidad, c.notas, c.fecha_precio, c.fuente_id, f.permiso
           FROM catalogo c JOIN fuentes f ON f.id = c.fuente_id"""
    ):
        texto = f"{r['descripcion']}. Categoría: {r['categoria'] or ''}. Unidad: {r['unidad']}. SKU {r['sku']}. {r['notas'] or ''}"
        filas.append((r["fuente_id"], "catalogo", f"catalogo:{r['sku']}", r["descripcion"], texto.strip(), r["permiso"], r["fecha_precio"]))

    for s in conn.execute(
        """SELECT s.codigo, s.servicio, s.tipo, s.unidad, s.zona, s.notas, s.fecha_precio, s.fuente_id, f.permiso
           FROM servicios s JOIN fuentes f ON f.id = s.fuente_id"""
    ):
        texto = f"{s['servicio']}. Tipo: {s['tipo']}. Unidad: {s['unidad']}. Zona: {s['zona'] or 'no aplica'}. {s['notas'] or ''}"
        filas.append((s["fuente_id"], "servicio", f"servicio:{s['codigo']}", s["servicio"], texto.strip(), s["permiso"], s["fecha_precio"]))

    for h in conn.execute(
        """SELECT h.id, h.folio, h.cliente, h.fecha, h.fuente_id, f.permiso
           FROM cotizaciones_historicas h JOIN fuentes f ON f.id = h.fuente_id"""
    ):
        partidas = conn.execute(
            "SELECT concepto, cantidad, unidad FROM partidas_historicas WHERE cotizacion_id = ? AND duplicada = 0 ORDER BY partida_num, id",
            (h["id"],),
        ).fetchall()
        lineas = "\n".join(f"- {p['concepto']} ({p['cantidad']:g} {p['unidad']})" for p in partidas)
        filas.append((h["fuente_id"], "historial", f"historial:{h['folio']}", f"{h['folio']} · {h['cliente']}",
                      f"Cotización {h['folio']} para {h['cliente']}.\n{lineas}", h["permiso"], h["fecha"]))

    for fi in conn.execute(
        """SELECT t.codigo, t.titulo, t.contenido_texto, t.fecha_carga, t.archivo_origen, t.fuente_id, f.permiso
           FROM fichas_tecnicas t JOIN fuentes f ON f.id = t.fuente_id"""
    ):
        clave = fi["codigo"] or fi["archivo_origen"]
        for n, trozo in enumerate(_trozos(fi["contenido_texto"]), start=1):
            filas.append((fi["fuente_id"], "ficha", f"ficha:{clave}#{n}", fi["titulo"], f"{fi['titulo']}\n{trozo}",
                          fi["permiso"], (fi["fecha_carga"] or "")[:10] or None))

    for fila in filas:
        cur = conn.execute(
            "INSERT INTO fragmentos (fuente_id, tipo, ref, titulo, texto, permiso, fecha) VALUES (?, ?, ?, ?, ?, ?, ?)", fila
        )
        conn.execute("INSERT INTO fragmentos_fts (rowid, texto, titulo) VALUES (?, ?, ?)", (cur.lastrowid, fila[4], fila[3]))
    conn.commit()
    return len(filas)
