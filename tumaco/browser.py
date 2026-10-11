from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from . import config

ARGS = [
    "--start-maximized",
    "--lang=es-CO",
    "--no-first-run",
    "--no-default-browser-check",
]

# Banderas que Playwright agrega por defecto y delatan la automatizacion:
# --enable-automation muestra la barra "Un software automatizado de pruebas esta controlando Chrome"
IGNORAR_ARGS = ["--enable-automation"]

# En lugar de --disable-blink-features=AutomationControlled (Chrome muestra un aviso de
# "marca no admitida"), se deja navigator.webdriver en false como en un Chrome normal.
SCRIPT_HUMANO = """
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false, configurable: true });
"""


def lanzar(p, headless: bool = False):
    """Lanza Chrome con perfil persistente y apariencia de navegador normal (sin proxy)."""
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(config.PROFILE_DIR),
        channel=config.BROWSER_CHANNEL,
        headless=headless,
        slow_mo=config.SLOW_MO,
        viewport=None,
        args=ARGS,
        ignore_default_args=IGNORAR_ARGS,
        chromium_sandbox=True,  # sin esto Chrome muestra el aviso de "--no-sandbox"
        locale="es-CO",
        timezone_id="America/Bogota",
        extra_http_headers={"Accept-Language": "es-CO,es;q=0.9,en;q=0.5"},
    )
    context.add_init_script(SCRIPT_HUMANO)
    return context


@contextmanager
def abrir_navegador():
    """Abre un navegador visible con perfil persistente y devuelve (context, page)."""
    with sync_playwright() as p:
        context = lanzar(p)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            yield context, page
        finally:
            context.close()
