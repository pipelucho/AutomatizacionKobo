r"""Prueba (solo lectura) la conexion al Chrome de la hoja: muestra el titulo y las pestanas de la hoja.

Uso:
    .venv\Scripts\python herramientas\probar_hoja.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tumaco.sheets import conectar_hoja  # noqa: E402


def main():
    with conectar_hoja() as hoja:
        print(f"Conectado a: {hoja.title()}")
        print(f"URL: {hoja.url}")
        pestanas = hoja.locator(".docs-sheet-tab-name").all_inner_texts()
        print(f"Pestanas de la hoja: {pestanas}")


if __name__ == "__main__":
    main()
