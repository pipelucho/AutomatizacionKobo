"""Interaccion con ritmo humano: pausas variables, mover el mouse antes de clic y escribir.

La velocidad se ajusta en .env: ESCALA_PAUSAS (1 = pausas completas, 0.3 = rapido, 0 = sin pausas)
y TECLEAR (1 = escribir tecla por tecla, 0 = pegar el texto de una vez).
"""
import random

from playwright.sync_api import Locator, Page

from . import config


def pausa(page: Page, minimo: float = 0.4, maximo: float = 1.2):
    if config.ESCALA_PAUSAS > 0:
        page.wait_for_timeout(random.uniform(minimo, maximo) * config.ESCALA_PAUSAS * 1000)


def clic(locator: Locator):
    locator.scroll_into_view_if_needed()
    locator.hover()
    pausa(locator.page, 0.2, 0.6)
    locator.click()


def escribir(locator: Locator, texto: str):
    """Borra el campo y escribe el texto: de una vez (rapido) o tecla por tecla si TECLEAR=1."""
    if not config.TECLEAR:
        pegar(locator, texto)
        return
    clic(locator)
    locator.fill("")
    locator.press_sequentially(texto, delay=random.randint(60, 160))
    pausa(locator.page, 0.2, 0.5)


def pegar(locator: Locator, texto: str):
    """Borra el campo y pone el texto de una sola vez, como al pegar con Ctrl+V.

    Se inserta directo en el campo (mismo efecto que pegar) sin pasar por el portapapeles
    de Windows, para no reemplazar lo que el usuario tenga copiado.
    """
    clic(locator)
    locator.fill("")
    pausa(locator.page, 0.2, 0.4)
    locator.page.keyboard.insert_text(texto)
    pausa(locator.page, 0.2, 0.5)
