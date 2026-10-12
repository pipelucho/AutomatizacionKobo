"""Carpetas por usuario dentro de CONTINGENCIAL y PDF del formulario (equivalente a Ctrl+P > Guardar como PDF)."""
import base64
import os
import re
import time
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

    t0 = time.monotonic()
    # Que las fotos de documentos anexos (cedulas, fachada...) esten cargadas antes de imprimir.
    # Solo esas: otras imagenes de la pagina pueden no cargar nunca y harian esperar de mas.
    # Las que no se han visto en pantalla pueden estar en carga diferida: se piden ya.
    page.evaluate("() => document.querySelectorAll('.file-preview img').forEach(i => { i.loading = 'eager'; })")
    try:
        page.wait_for_function(
            "() => [...document.querySelectorAll('.file-preview img')].filter(i => i.getAttribute('src'))"
            ".every(i => i.complete && i.naturalWidth > 0)",
            timeout=20_000, polling=300)
    except Exception:
        print("   (alguna foto de documento no termino de cargar; se imprime igual)")
    t_fotos = time.monotonic()

    # Activar el modo impresion para que el formulario acomode su diseño como con Ctrl+P
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.emulate_media(media="print")
    page.wait_for_timeout(800)
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
        # OJO: media=None NO quita la emulacion (Playwright no envia el parametro) y la pagina
        # queda en modo impresion, donde Enketo oculta el pie con el boton ENVIAR. "null" la quita.
        page.emulate_media(media="null")
        page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
        page.wait_for_timeout(300)
    t_imprimir = time.monotonic()

    archivo = _ruta_larga(destino)
    if archivo.exists():
        print(f"   (se reemplaza el PDF anterior: {destino.name})")
    contenido = base64.b64decode(resultado["data"])
    archivo.write_bytes(contenido)
    print(f"   PDF guardado: {destino}")
    print(f"   ({len(contenido) / 1e6:.1f} MB | fotos {t_fotos - t0:.0f}s, imprimir {t_imprimir - t_fotos:.0f}s, "
          f"guardar {time.monotonic() - t_imprimir:.0f}s)")
    return destino


def _ruta_larga(ruta: Path) -> Path:
    """En Windows una ruta de 260+ caracteres falla al guardar (pasa con el nombre largo del formulario 4
    dentro de carpetas profundas); el prefijo \\\\?\\ quita ese limite."""
    absoluta = str(ruta.resolve())
    if os.name == "nt" and len(absoluta) >= 240 and not absoluta.startswith("\\\\?\\"):
        return Path("\\\\?\\" + absoluta)
    return ruta


def guardar_documento(carpeta: Path, cara: bytes, reverso: bytes) -> Path:
    """DOCUMENTO.pdf: una hoja carta con la cara de la cedula arriba y el reverso abajo, centradas."""
    from io import BytesIO

    from PIL import Image

    dpi = 150
    hoja = Image.new("RGB", (int(8.5 * dpi), int(11 * dpi)), "white")
    ancho = int(4.7 * dpi)  # ~12 cm, como el ejemplo
    for datos, arriba in ((cara, 1.0), (reverso, 6.7)):  # pulgadas desde el borde superior
        img = Image.open(BytesIO(datos)).convert("RGB")
        img = img.resize((ancho, round(ancho * img.height / img.width)), Image.LANCZOS)
        hoja.paste(img, ((hoja.width - ancho) // 2, int(arriba * dpi)))
    destino = carpeta / "DOCUMENTO.pdf"
    hoja.save(destino, "PDF", resolution=dpi, quality=90)
    print(f"   Cedula guardada en un solo PDF: {destino}")
    return destino
