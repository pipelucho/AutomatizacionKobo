r"""Analiza (solo lectura) lo ya enviado a Kobo con las reglas de nombre y casa, y muestra que corregir.

Compara cada formulario enviado con el Excel y la hoja de Google, usando los valores originales de
los logs cuando existen. No cambia nada: deja la lista en salida\analisis_correcciones.json para
herramientas\corregir.py.

Uso (con el bot cerrado y el Chrome de la hoja abierto):
    .venv\Scripts\python herramientas\analizar.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from tumaco import analisis, excel, sheets  # noqa: E402
from tumaco.browser import lanzar  # noqa: E402


def main():
    tabla = excel.cargar_tabla()
    with sync_playwright() as p:
        print("Leyendo la hoja de Google...")
        filas_hoja = sheets.leer_filas(sheets.Hoja(p).pestana())
        print("Descargando los envios de Kobo...")
        contexto = lanzar(p, headless=True)  # solo consultas a la API, sin ventana
        try:
            envios = analisis.descargar_envios(contexto.request)
        finally:
            contexto.close()
    resultado = analisis.analizar(tabla, envios, filas_hoja)
    print(analisis.resumen(resultado))


if __name__ == "__main__":
    main()
