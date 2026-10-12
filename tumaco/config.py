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
SLOW_MO = int(os.getenv("SLOW_MO", "0"))
# Pausas al azar entre pasos (1 = completas, 0.3 = rapido, 0 = sin pausas) y escritura tecla por tecla (1) o pegada (0)
ESCALA_PAUSAS = float(os.getenv("ESCALA_PAUSAS", "0.3"))
TECLEAR = os.getenv("TECLEAR", "0") == "1"
# Lado mayor (px) de las fotos al imprimir el PDF: se ven igual en carta y el PDF pesa y tarda mucho menos
FOTOS_PDF_MAX = int(os.getenv("FOTOS_PDF_MAX", "1600"))

# Perfil persistente: la sesion de Kobo (y luego Google) queda guardada entre ejecuciones
PROFILE_DIR = ROOT / ".browser_profile"

EXCEL_PATH = ROOT / os.getenv("EXCEL_PATH", "USUARIOS.xlsx")
KOBO_COLUMNA_USUARIO = os.getenv("KOBO_COLUMNA_USUARIO", "persona atendida+usuario")
DEBUG_DIR = OUTPUT_DIR / "debug"
# Capturas de pantalla de la tabla en cada intento de busqueda (lentas); los JSON siempre se guardan
DEBUG_CAPTURAS = os.getenv("DEBUG_CAPTURAS", "0") == "1"

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

# Carpeta base donde se crea una subcarpeta por usuario (USUARIO_NOMBRE) con los PDF
CONTINGENCIAL_DIR = ROOT / os.getenv("CONTINGENCIAL_DIR", "CONTINGENCIAL")
# Personas terminadas sin problemas (herramientas/terminados.py las mueve aqui)
TERMINADOS_DIR = CONTINGENCIAL_DIR / os.getenv("TERMINADOS_DIR", "TERMINADOS")
# Fecha/titulo arriba y direccion/pagina abajo en el PDF, como Ctrl+P en Chrome (1 = si, 0 = no)
PDF_ENCABEZADOS = os.getenv("PDF_ENCABEZADOS", "1") == "1"

# Hoja de calculo de Google que se actualiza al final (la sesion de Google queda en el perfil del navegador)
GOOGLE_SHEET_URL = os.getenv(
    "GOOGLE_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/1sKzEkMpefgbGclUG54sgASOmp6Dr7EJR/edit#gid=1042612756")

# Chrome abierto a mano por el usuario (con su sesion de Google) al que el bot se conecta para la hoja.
# Se abre con: chrome.exe --remote-debugging-port=9222 --user-data-dir=%LOCALAPPDATA%\TumacoChrome
CHROME_DEPURACION_URL = os.getenv("CHROME_DEPURACION_URL", "http://127.0.0.1:9222")

# Registro de casos por resolver (no encontrados, dudosos, sin formulario 4...), se actualiza en cada corrida
CASOS_PATH = ROOT / os.getenv("CASOS_PATH", "CASOS.xlsx")

# Cuando Kobo, el Excel y la hoja no coinciden en nombre o casa: 1 = preguntar en una ventana en el
# momento (no quedan correcciones para despues); 0 = aplicar la regla y dejar aviso en CASOS.xlsx
PREGUNTAR_DUDAS = os.getenv("PREGUNTAR_DUDAS", "1") == "1"
