"""Carpetas por usuario dentro de CONTINGENCIAL y PDF del formulario (equivalente a Ctrl+P > Guardar como PDF)."""
import base64
import re
from pathlib import Path

from playwright.sync_api import Page

from . import config

# Encabezado y pie como los de Chrome al imprimir: fecha y titulo arriba, direccion y pagina abajo
_ESTILO = "font-size:8px;font-family:Arial,sans-serif;width:100%;padding:0 10mm;display:flex;justify-content:space-between"
ENCABEZADO = f'<div style="{_ESTILO}"><span class="date"></span><span class="title"></span><span></span></div>'
PIE = (f'<div style="{_ESTILO}"><span class="url"></span>'
       '<span><span class="pageNumber"></span>/<span class="totalPages"></span></span></div>')


def nombre_valido(texto: str) -> str:
    """Quita los caracteres que Windows no permite en nombres de archivo/carpeta (como hace Chrome)."""
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto)
    return re.sub(r"\s+", " ", texto).strip().rstrip(".")


def carpeta_usuario(numero_usuario: str, nombre: str) -> Path:
    """CONTINGENCIAL/<USUARIO>_<NOMBRE>, ej. CONTINGENCIAL/790_LUZ MARÍA OBANDO"""
    carpeta = config.CONTINGENCIAL_DIR / nombre_valido(f"{numero_usuario}_{nombre.strip().upper()}")
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def guardar_pdf(page: Page, carpeta: Path) -> Path:
    """Imprime la pagina tal como esta (con las correcciones) y la guarda con el nombre por defecto de Chrome,
    que es el titulo de la pagina: '1. FORMATO REGISTRO DE VISITA PUERTA A PUERTA.pdf'."""
    titulo = nombre_valido(page.title()) or "formulario"
    destino = carpeta / f"{titulo}.pdf"

    # Activar el modo impresion para que el formulario acomode su diseño como con Ctrl+P
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.emulate_media(media="print")
    page.wait_for_timeout(1500)
    try:
        cdp = page.context.new_cdp_session(page)
        resultado = cdp.send("Page.printToPDF", {
            "paperWidth": 8.5, "paperHeight": 11,  # carta
            "marginTop": 0.4, "marginBottom": 0.4, "marginLeft": 0.4, "marginRight": 0.4,
            "printBackground": False,
            "displayHeaderFooter": config.PDF_ENCABEZADOS,
            "headerTemplate": ENCABEZADO,
            "footerTemplate": PIE,
            "preferCSSPageSize": True,
        })
        cdp.detach()
    finally:
        page.emulate_media(media=None)
        page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")

    if destino.exists():
        print(f"   (se reemplaza el PDF anterior: {destino.name})")
    destino.write_bytes(base64.b64decode(resultado["data"]))
    print(f"   PDF guardado: {destino}")
    return destino
