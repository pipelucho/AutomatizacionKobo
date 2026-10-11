import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KOBO_URL = os.getenv("KOBO_URL", "https://eu.kobotoolbox.org").rstrip("/")
KOBO_USER = os.getenv("KOBO_USER", "")
KOBO_PASS = os.getenv("KOBO_PASS", "")
OUTPUT_DIR = ROOT / os.getenv("OUTPUT_DIR", "salida")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome") or None
# Pausa (ms) entre acciones del navegador para poder seguirlas con la vista; 0 = maxima velocidad
SLOW_MO = int(os.getenv("SLOW_MO", "100"))

# Perfil persistente: la sesion de Kobo (y luego Google) queda guardada entre ejecuciones
PROFILE_DIR = ROOT / ".browser_profile"

EXCEL_PATH = ROOT / os.getenv("EXCEL_PATH", "USUARIOS.xlsx")
KOBO_COLUMNA_USUARIO = os.getenv("KOBO_COLUMNA_USUARIO", "persona atendida+usuario")
DEBUG_DIR = OUTPUT_DIR / "debug"

# Formularios a revisar por cliente, en orden (se buscan por el inicio del nombre del proyecto)
FORMULARIOS = [
    "1. FORMATO REGISTRO DE VISITA PUERTA A PUERTA",
    "2. MANIFESTACIÓN DE VOLUNTAD Y AUTORIZACIÓN",
    "3. ENCUESTA DE CARACTERIZACIÓN SOCIOECONÓMICA",
    "4. FORMATO ACTA DE VERIFICACIÓN DEL ESTADO INICIAL",
]

# Columnas de respaldo si no se encuentra por USUARIO
KOBO_COLUMNA_CASA = os.getenv("KOBO_COLUMNA_CASA", "persona atendida+direccion")
KOBO_COLUMNA_NOMBRE = os.getenv("KOBO_COLUMNA_NOMBRE", "persona atendida+nombre")

# Columnas elegidas a mano por formulario (se recuerdan entre ejecuciones)
COLUMNAS_PATH = ROOT / "columnas.json"

# Trazos de firmas (generados con herramientas/firma_desde_imagen.py)
FIRMAS_DIR = ROOT / "firmas"
