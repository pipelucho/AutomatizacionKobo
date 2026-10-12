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
    bases = [b for b in (config.CONTINGENCIAL_DIR, config.TERMINADOS_DIR) if b.is_dir()]
    carpetas = ([next((b / n for b in bases if (b / n).is_dir()), bases[0] / n) for n in nombres] if nombres
                else sorted((c for b in bases for c in b.iterdir()
                             if c.is_dir() and c.name.split("_")[0].isdigit()),  # solo carpetas de personas
                            key=lambda c: c.name))
    for carpeta in carpetas:
        print(carpeta.name)
        pdf.unir_pdfs(carpeta)


if __name__ == "__main__":
    main()
