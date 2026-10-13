"""Procesamiento aparte: el mismo bot que main.py, sin tocar la hoja de Google y con sus propios archivos.

- Usuarios de USUARIOS_APARTE.xlsx; sus carpetas quedan en CONTINGENCIAL_APARTE/.
- Lo que iria en la hoja de Google queda en HOJA_APARTE.xlsx (mismas columnas; RESPONSABLE en blanco).
- ENTRADA_APARTE/<usuario>/ trae los archivos que reemplazan los de Kobo: CEDULA_CARA.jpg, CEDULA_REVERSO.jpg
  (formulario 2) y FACTURA.jpg (soporte de propiedad del formulario 1).
- Casos, marcas pendientes y registros van a CASOS_APARTE.xlsx y salida_aparte/ (no se mezclan con los otros).

Uso: .venv\\Scripts\\python aparte.py [--limite N]
"""
import os

# Antes de cargar la configuracion: estas variables mandan sobre las de .env
os.environ.update({
    "EXCEL_PATH": "USUARIOS_APARTE.xlsx",
    "CONTINGENCIAL_DIR": "CONTINGENCIAL_APARTE",
    "HOJA_LOCAL": "HOJA_APARTE.xlsx",
    "ENTRADA_DIR": "ENTRADA_APARTE",
    "CASOS_PATH": "CASOS_APARTE.xlsx",
    "OUTPUT_DIR": "salida_aparte",
})

import main  # noqa: E402

if __name__ == "__main__":
    main.main()
