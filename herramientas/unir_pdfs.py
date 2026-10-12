r"""Une los PDF de cada usuario en CONTINGENCIAL en un solo archivo con el nombre de su carpeta.

El bot ya lo hace al terminar a cada persona; esto sirve para rehacerlo a mano o para
las carpetas de personas terminadas antes de tener esta funcion.

Uso:
    .venv\Scripts\python herramientas\unir_pdfs.py                    (todas las carpetas)
    .venv\Scripts\python herramientas\unir_pdfs.py "498_BIOLINDA BELARCAZAR"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tumaco import config, pdf  # noqa: E402


def main():
    nombres = sys.argv[1:]
    carpetas = ([config.CONTINGENCIAL_DIR / n for n in nombres] if nombres
                else sorted(c for c in config.CONTINGENCIAL_DIR.iterdir() if c.is_dir()))
    for carpeta in carpetas:
        print(carpeta.name)
        pdf.unir_pdfs(carpeta)


if __name__ == "__main__":
    main()
