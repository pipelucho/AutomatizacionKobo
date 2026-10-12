r"""Actualiza CASOS.xlsx con los casos por resolver y los muestra agrupados por tipo.

El bot lo hace solo al final de cada corrida; esto sirve para verlo sin correr el bot
(por ejemplo, despues de corregir algo a mano en el Excel). Abre CASOS.xlsx para trabajarlos:
pestana 'Casos' (uno por fila, con que hacer) y 'Resumen' (cuantos hay de cada tipo).

Uso:
    .venv\Scripts\python herramientas\casos.py
"""
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tumaco import casos, config, excel  # noqa: E402


def main():
    filas = casos.actualizar(excel.cargar_tabla())
    if filas is None:
        return
    pendientes = [f for f in filas if f["Estado"] == casos.PENDIENTE]
    for tipo, grupo in groupby(pendientes, key=lambda f: f["Tipo"]):
        grupo = list(grupo)
        print(f"\n{tipo} ({len(grupo)}): {casos.QUE_HACER.get(tipo, '')}")
        for f in grupo:
            print(f"   - fila {f['Fila Excel']} | {f['Usuario']} {f['Nombre']} | {f['Formulario']}: {str(f['Detalle'])[:100]}")
    print(f"\n{casos.resumen(filas)}")
    print(f"Archivo: {config.CASOS_PATH}")


if __name__ == "__main__":
    main()
