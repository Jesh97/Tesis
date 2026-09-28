"""Tests de la extracción de PDF en scripts/analyze_news.py (reportes de la
Marina de Guerra del Perú/DICAPI, además de noticias en HTML). Genera PDFs de
prueba en memoria con reportlab (dependencia solo de test, no del pipeline en
sí -- ver requirements.txt) en vez de depender de un archivo fixture externo.
No hace red ni toca la base de datos: prueba _es_pdf y _extraer_de_pdf en
aislamiento, igual que test_extraccion_reglas.py prueba la extracción local
sin depender de que la fuente haya sido HTML o PDF."""
from io import BytesIO

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import analyze_news
import extraccion_reglas


def _pdf_con_texto(lineas: list[str], titulo: str | None = None) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    if titulo is not None:
        # reportlab guarda un título "Untitled" por defecto si nunca se llama
        # a setTitle -- pasar "" (a diferencia de None) sí produce un PDF sin
        # metadata de título, para poder probar el fallback al nombre del
        # archivo en la URL.
        c.setTitle(titulo)
    y = 750
    for linea in lineas:
        c.drawString(50, y, linea)
        y -= 20
    c.save()
    return buffer.getvalue()


def _pdf_sin_texto() -> bytes:
    """Simula un PDF escaneado (una página sin ningún texto seleccionable,
    como si fuera solo una imagen) -- este pipeline no hace OCR."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.rect(50, 50, 100, 100)  # una forma dibujada, cero texto
    c.save()
    return buffer.getvalue()


REPORTE_DICAPI = [
    "MARINA DE GUERRA DEL PERU - DICAPI",
    "REPORTE DE INCIDENTE PESQUERO",
    "",
    "El dia 20 de septiembre de 2026, la embarcacion pesquera",
    "denominada Don Lucho III, con matricula PL-8842-CM, fue",
    "detectada realizando faenas de pesca de arrastre dentro de",
    "la zona reservada de las 5 millas frente a las costas de",
    "Puerto Eten, Lambayeque, en clara infraccion a la normativa",
    "pesquera vigente. Se notifico a las autoridades de PRODUCE",
    "para las acciones correspondientes.",
]


class TestEsPdf:
    def test_por_content_type(self):
        assert analyze_news._es_pdf("application/pdf; charset=binary", "https://x.com/reporte") is True

    def test_por_extension_de_url_sin_importar_mayusculas(self):
        assert analyze_news._es_pdf("text/html", "https://x.com/reporte.PDF?token=abc") is True

    def test_html_normal_no_es_pdf(self):
        assert analyze_news._es_pdf("text/html; charset=utf-8", "https://x.com/noticia") is False


class TestExtraerDePdf:
    def test_extrae_titulo_desde_la_metadata_del_pdf(self):
        contenido = _pdf_con_texto(REPORTE_DICAPI, titulo="Reporte de Incidente DICAPI-2026-014")
        titulo, texto = analyze_news._extraer_de_pdf(contenido, "https://marina.mil.pe/reportes/incidente.pdf")
        assert titulo == "Reporte de Incidente DICAPI-2026-014"
        assert "Don Lucho III" in texto
        assert "PL-8842-CM" in texto

    def test_sin_metadata_usa_el_nombre_del_archivo_en_la_url(self):
        contenido = _pdf_con_texto(REPORTE_DICAPI, titulo="")
        titulo, _texto = analyze_news._extraer_de_pdf(
            contenido, "https://marina.mil.pe/reportes/incidente-dicapi-2026-014.pdf"
        )
        assert titulo == "incidente dicapi 2026 014"

    def test_pdf_escaneado_sin_texto_lanza_valueerror_explicando_que_no_hay_ocr(self):
        contenido = _pdf_sin_texto()
        with pytest.raises(ValueError, match="no hace OCR"):
            analyze_news._extraer_de_pdf(contenido, "https://marina.mil.pe/reportes/escaneado.pdf")

    def test_pdf_corrupto_lanza_valueerror(self):
        with pytest.raises(ValueError, match="No se pudo leer el PDF"):
            analyze_news._extraer_de_pdf(b"esto no es un PDF valido", "https://x.com/roto.pdf")


def test_el_texto_extraido_del_pdf_fluye_sin_cambios_por_la_extraccion_local():
    """Confirma que extraccion_reglas.py (el fallback sin Claude) no necesitó
    ningún cambio: ya trabaja sobre texto plano sin que le importe si vino de
    HTML o de un PDF."""
    contenido = _pdf_con_texto(REPORTE_DICAPI, titulo="Reporte de Incidente DICAPI-2026-014")
    titulo, texto = analyze_news._extraer_de_pdf(contenido, "https://marina.mil.pe/reportes/incidente.pdf")

    resultado = extraccion_reglas.extraer(titulo, texto)

    assert resultado.es_relevante is True
    assert resultado.tipo_infraccion == "Pesca en Zona Prohibida"
    assert resultado.matricula_detectada == "PL-8842-CM"
    assert resultado.ubicacion_estimada == "Puerto Eten"
