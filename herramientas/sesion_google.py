r"""Abre la hoja de Google en el navegador del bot para iniciar sesion UNA vez, a mano.

La sesion queda guardada en el perfil del bot (.browser_profile) y despues el bot entra
solo a la hoja. La contrasena la escribes tu en la ventana: no se guarda en ningun archivo.
No lo corras mientras el bot (main.py) este abierto: comparten el mismo navegador.

Uso:
    .venv\Scripts\python herramientas\sesion_google.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from tumaco import config  # noqa: E402
from tumaco.browser import lanzar  # noqa: E402


def main():
    with sync_playwright() as p:
        context = lanzar(p)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.GOOGLE_SHEET_URL)
        print("Si Google pide iniciar sesion, hazlo en la ventana de Chrome que se abrio.")
        input("Cuando veas la hoja de calculo abierta, presiona Enter aqui...")
        if "docs.google.com/spreadsheets" in page.url and "accounts.google.com" not in page.url:
            print(f"Listo: hoja abierta ({page.title()}). La sesion quedo guardada para el bot.")
        else:
            print(f"La hoja no quedo abierta (pagina actual: {page.url}). Intentalo de nuevo.")
        context.close()


if __name__ == "__main__":
    main()
