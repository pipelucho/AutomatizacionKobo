"""Conexion al Chrome que el usuario abre a mano con su sesion de Google, para trabajar en la hoja.

El bot no inicia sesion en Google: se conecta a una ventana de Chrome ya abierta y con la hoja
cargada (ver herramientas/abrir_chrome_hoja.ps1). Al terminar solo se desconecta; la ventana sigue abierta.
"""
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

from . import config


@contextmanager
def conectar_hoja():
    """Devuelve la pestana de la hoja de calculo del Chrome abierto por el usuario."""
    with sync_playwright() as p:
        try:
            navegador = p.chromium.connect_over_cdp(config.CHROME_DEPURACION_URL)
        except Exception as e:
            raise RuntimeError(
                "No encontre el Chrome de la hoja abierto. Abrelo con herramientas\abrir_chrome_hoja.ps1, "
                "inicia sesion en Google y deja la hoja abierta.") from e
        yield buscar_pestana_hoja(navegador)
        # Sin navegador.close(): conectado por CDP solo se desconecta, la ventana del usuario sigue abierta


def buscar_pestana_hoja(navegador) -> Page:
    id_hoja = config.GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]
    pestanas = [pg for ctx in navegador.contexts for pg in ctx.pages]
    for pagina in pestanas:
        if id_hoja in pagina.url:
            return pagina
    abiertas = "\n".join(f"   - {pg.url[:100]}" for pg in pestanas) or "   (ninguna)"
    raise RuntimeError(f"El Chrome de la hoja esta abierto pero sin la hoja. Pestanas abiertas:\n{abiertas}")
