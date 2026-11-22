"""Pruebas de la lectura de adjuntos y del conteo de tokens multimodal. Sin red ni claves."""

from __future__ import annotations

import pytest
from openpyxl import Workbook
from reportlab.pdfgen import canvas

from agent.llm.adjuntos import ErrorAdjunto, construir_contenido, leer_adjunto
from agent.llm.tokens import recortar_historial

# PNG de 1x1 píxel válido.
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201a5f645400000000049454e44ae426082"
)


def test_texto_utf8_y_cp1252(tmp_path):
    (tmp_path / "a.txt").write_text("Cemento gris 50 kg: $245.00 MXN", encoding="utf-8")
    (tmp_path / "b.txt").write_bytes("Varilla 3/8\" — ñandú".encode("cp1252", errors="replace"))
    assert "Cemento gris" in leer_adjunto(tmp_path / "a.txt").texto
    assert "Varilla" in leer_adjunto(tmp_path / "b.txt").texto


def test_csv_con_punto_y_coma(tmp_path):
    (tmp_path / "c.csv").write_text("codigo;nombre;precio\nCEM-01;Cemento;245\n", encoding="utf-8")
    a = leer_adjunto(tmp_path / "c.csv")
    assert "CEM-01 | Cemento | 245" in a.texto
    assert "2 filas" in a.detalle


def test_excel_lee_todas_las_hojas_e_ignora_filas_vacias(tmp_path):
    wb = Workbook()
    wb.active.title = "Ventas"
    wb.active.append(["cliente", "total"])
    wb.active.append([None, None])
    wb.active.append(["Obra Norte", 1200])
    wb.create_sheet("Notas").append(["precio viejo"])
    wb.save(tmp_path / "x.xlsx")
    a = leer_adjunto(tmp_path / "x.xlsx")
    assert "## Hoja: Ventas" in a.texto and "Obra Norte | 1200" in a.texto and "## Hoja: Notas" in a.texto
    assert "2 hojas, 3 filas" in a.detalle


def test_pdf_con_texto(tmp_path):
    c = canvas.Canvas(str(tmp_path / "f.pdf"))
    c.drawString(72, 700, "Cable THW calibre 12")
    c.save()
    a = leer_adjunto(tmp_path / "f.pdf")
    assert "Cable THW" in a.texto and "1 páginas" in a.detalle


def test_pdf_sin_texto_da_error_claro(tmp_path):
    c = canvas.Canvas(str(tmp_path / "vacio.pdf"))
    c.showPage()
    c.save()
    with pytest.raises(ErrorAdjunto, match="escaneo"):
        leer_adjunto(tmp_path / "vacio.pdf")


def test_recorte_por_caracteres(tmp_path):
    (tmp_path / "g.txt").write_text("x" * 500, encoding="utf-8")
    a = leer_adjunto(tmp_path / "g.txt", max_caracteres=100)
    assert a.truncado and a.caracteres_originales == 500 and "recortado" in a.texto


def test_errores_de_archivo(tmp_path):
    with pytest.raises(ErrorAdjunto, match="No existe"):
        leer_adjunto(tmp_path / "nada.txt")
    (tmp_path / "z.exe").write_bytes(b"MZ")
    with pytest.raises(ErrorAdjunto, match="no soportado"):
        leer_adjunto(tmp_path / "z.exe")
    (tmp_path / "e.txt").write_text("   \n", encoding="utf-8")
    with pytest.raises(ErrorAdjunto, match="no contiene texto"):
        leer_adjunto(tmp_path / "e.txt")


def test_ruta_entre_comillas(tmp_path):
    (tmp_path / "h.txt").write_text("hola", encoding="utf-8")
    assert leer_adjunto(f'"{tmp_path / "h.txt"}"').texto == "hola"


def test_imagen_se_envia_como_image_url(tmp_path):
    (tmp_path / "i.png").write_bytes(PNG_1X1)
    img = leer_adjunto(tmp_path / "i.png")
    assert img.tipo == "imagen" and img.data_url.startswith("data:image/png;base64,")
    contenido = construir_contenido("¿Qué ves?", [img])
    assert [p["type"] for p in contenido] == ["text", "image_url"]
    assert contenido[1]["image_url"]["url"] == img.data_url


def test_contenido_solo_texto_rotula_el_archivo(tmp_path):
    (tmp_path / "n.txt").write_text("dato", encoding="utf-8")
    contenido = construir_contenido("pregunta", [leer_adjunto(tmp_path / "n.txt")])
    assert isinstance(contenido, str)
    assert "[ARCHIVO: n.txt]" in contenido and contenido.endswith("pregunta")


def test_recorte_de_historial_no_cuenta_base64_como_texto():
    base64_enorme = "A" * 2_000_000
    imagen = {"role": "user", "content": [
        {"type": "text", "text": "mira"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_enorme}"}},
    ]}
    historial = [imagen, {"role": "assistant", "content": "ok"}, {"role": "user", "content": "otra cosa"}]
    # Con el base64 contado como texto, el turno de la imagen (~670,000 tokens) se descartaría.
    assert recortar_historial(historial, 3000) == historial
