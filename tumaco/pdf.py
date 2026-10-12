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


def carpeta_persona(usuario, nombre_final: str = "") -> Path:
    """Carpeta de la persona: <USUARIO>_<nombre final> si quien atendio es otra persona que la del Excel
    (columna L), si no <USUARIO>_<nombre del Excel>.

    Si la carpeta ya existia con el nombre del Excel y ahora hay nombre final, se renombra (sus PDF se
    conservan) y se borra el PDF unido con el nombre viejo, para que no queden documentos en dos carpetas.
    """
    final = (nombre_final or getattr(usuario, "nombre_final", "") or "").strip()
    destino = config.CONTINGENCIAL_DIR / nombre_valido(f"{usuario.usuario}_{(final or usuario.nombre).strip().upper()}")
    vieja = config.CONTINGENCIAL_DIR / nombre_valido(f"{usuario.usuario}_{usuario.nombre.strip().upper()}")
    # Si ya estaba en TERMINADOS y se va a cambiar algo, vuelve a CONTINGENCIAL (no se crea otra carpeta)
    for carpeta in (vieja, destino):
        terminada = config.TERMINADOS_DIR / carpeta.name
        if terminada.is_dir() and not carpeta.exists():
            terminada.rename(carpeta)
            print(f"   Carpeta devuelta de TERMINADOS a CONTINGENCIAL: {carpeta.name}")
    if final and vieja.exists() and vieja != destino:
        destino.mkdir(parents=True, exist_ok=True)
        for archivo in vieja.iterdir():
            nuevo = destino / archivo.name
            if not nuevo.exists() or archivo.stat().st_mtime > nuevo.stat().st_mtime:
                archivo.replace(nuevo)  # se queda el mas reciente
            else:
                archivo.unlink()
        vieja.rmdir()
        (destino / f"{vieja.name}.pdf").unlink(missing_ok=True)  # PDF unido con el nombre viejo
        print(f"   Carpeta renombrada: {vieja.name} -> {destino.name}")
    destino.mkdir(parents=True, exist_ok=True)
    return destino


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
    # Fotos de celular a tamaño de impresion (solo para el PDF; despues se restauran): en carta se ven
    # igual y el PDF pasa de decenas de MB y minutos a pocos MB y segundos. En Kobo no cambia nada.
    reducidas = page.evaluate(_JS_REDUCIR_FOTOS, config.FOTOS_PDF_MAX) if config.FOTOS_PDF_MAX > 0 else 0
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
        if reducidas:
            page.evaluate(_JS_RESTAURAR_FOTOS)
        page.wait_for_timeout(300)
    t_imprimir = time.monotonic()

    archivo = _ruta_larga(destino)
    if archivo.exists():
        print(f"   (se reemplaza el PDF anterior: {destino.name})")
    contenido = base64.b64decode(resultado["data"])
    archivo.write_bytes(contenido)
    print(f"   PDF guardado: {destino}")
    print(f"   ({len(contenido) / 1e6:.1f} MB | {reducidas} foto(s) reducida(s) | fotos {t_fotos - t0:.0f}s, imprimir {t_imprimir - t_fotos:.0f}s, "
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


# Orden de los documentos en el PDF unido: prefijo del nombre del archivo
ORDEN_UNION = ["1.", "DOCUMENTO", "2.", "3.", "4."]


def unir_pdfs(carpeta: Path) -> Path | None:
    """Une los PDF de la carpeta del usuario en un solo archivo con el nombre de la carpeta,
    ej. 498_BIOLINDA BELARCAZAR.pdf, en el orden 1, DOCUMENTO, 2, 3, 4 (los que existan)."""
    from pypdf import PdfWriter

    destino = carpeta / f"{carpeta.name}.pdf"
    archivos = sorted(f for f in carpeta.glob("*.pdf") if f.name != destino.name)
    partes = []
    for prefijo in ORDEN_UNION:
        partes += [f for f in archivos if f.name.upper().startswith(prefijo) and f not in partes]
    if not partes:
        print(f"   No hay PDF para unir en {carpeta.name}")
        return None

    union = PdfWriter()
    for parte in partes:
        with _ruta_larga(parte).open("rb") as f:
            union.append(f)
    with _ruta_larga(destino).open("wb") as f:
        union.write(f)
    union.close()
    print(f"   PDF unido ({len(partes)} documentos): {destino}")
    for parte in partes:
        print(f"     - {parte.name}")
    return destino


# Reduce las fotos cargadas en el formulario (vista previa) a `maximo` px de lado mayor, en JPEG.
# Guarda la direccion original para restaurarla despues de imprimir. Devuelve cuantas redujo.
_JS_REDUCIR_FOTOS = r"""
async (maximo) => {
  let n = 0;
  for (const img of document.querySelectorAll('.file-preview img')) {
    const lado = Math.max(img.naturalWidth, img.naturalHeight);
    if (!img.complete || !lado || lado <= maximo || img.dataset.tumacoSrc) continue;
    try {
      const escala = maximo / lado;
      const c = document.createElement('canvas');
      c.width = Math.round(img.naturalWidth * escala);
      c.height = Math.round(img.naturalHeight * escala);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      const url = c.toDataURL('image/jpeg', 0.85);  // falla si la foto es de otro dominio: se deja igual
      img.dataset.tumacoSrc = img.src;
      img.src = url;
      await img.decode().catch(() => {});
      n++;
    } catch (e) { /* se imprime la original */ }
  }
  return n;
}
"""

_JS_RESTAURAR_FOTOS = r"""
() => document.querySelectorAll('img[data-tumaco-src]').forEach(img => {
  img.src = img.dataset.tumacoSrc;
  delete img.dataset.tumacoSrc;
})
"""
