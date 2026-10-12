"""Hoja de Google 'Tumaco': se llena con los datos del Excel de usuarios.

El bot no inicia sesion en Google: se conecta a una ventana de Chrome ya abierta y con la hoja
cargada (ver herramientas/abrir_chrome_hoja.ps1). Al terminar solo se desconecta; la ventana sigue abierta.

La hoja se dibuja como imagen (no se pueden leer las celdas de la pagina), asi que se lee
descargandola en CSV con la misma sesion y se escribe como una persona: ir a la celda con el
cuadro de nombre (arriba a la izquierda), escribir y Enter.
"""
import csv
import io
import random
import re
import time
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

from . import config, reglas
from .texto import numeros_casa, similitud_nombre

PESTANA = "Tumaco"
FILA_ENCABEZADOS = 16  # No. | NOMBRES Y APELLIDOS USUARIO INICIAL | ... | RESPONSABLE
RESPONSABLE = "KAREN QUIÑONES"
# Columnas de la hoja (A = No. del usuario, E = direccion inicial)
COL_NUMERO, COL_DIRECCION_INICIAL = "A", "E"
COL_NOMBRE, COL_DOCUMENTO, COL_DIRECCION, COL_VERIFICACION, COL_SOPORTE, COL_RESPONSABLE = "F", "G", "H", "I", "J", "K"
COL_OBSERVACION = "L"  # razon del estado (ej. 'NUEVO PROPIETARIO'; en RETIRADO la inviabilidad)
OBSERVACION_RETIRADO = "INVIABILIDAD VIVIENDA INEXISTENTE"  # el texto que ya usan otros para los lotes vacios


class Hoja:
    """Conexion (una por corrida) al Chrome de la hoja; se reconecta si la ventana se cerro y se reabrio.

    Nunca se cierra ese navegador: es la ventana del usuario con su sesion de Google.
    """

    def __init__(self, playwright):
        self._p = playwright
        self._navegador = None

    def pestana(self) -> Page:
        if self._navegador is None or not self._navegador.is_connected():
            try:
                self._navegador = self._p.chromium.connect_over_cdp(config.CHROME_DEPURACION_URL)
            except Exception as e:
                raise RuntimeError(
                    "No encontre el Chrome de la hoja abierto. Abrelo con herramientas\\abrir_chrome_hoja.ps1, "
                    "inicia sesion en Google y deja la hoja abierta.") from e
        return buscar_pestana_hoja(self._navegador)


@contextmanager
def conectar_hoja():
    """Devuelve la pestana de la hoja de calculo del Chrome abierto por el usuario (para herramientas).
    Al salir solo se desconecta: la ventana del usuario sigue abierta."""
    with sync_playwright() as p:
        yield Hoja(p).pestana()


def buscar_pestana_hoja(navegador) -> Page:
    pestanas = [pg for ctx in navegador.contexts for pg in ctx.pages]
    for pagina in pestanas:
        if _id_hoja() in pagina.url:
            return pagina
    abiertas = "\n".join(f"   - {pg.url[:100]}" for pg in pestanas) or "   (ninguna)"
    raise RuntimeError(f"El Chrome de la hoja esta abierto pero sin la hoja. Pestanas abiertas:\n{abiertas}")


def _id_hoja() -> str:
    return config.GOOGLE_SHEET_URL.split("/d/")[1].split("/")[0]


# ---------- Lectura ----------

def leer_filas(hoja: Page) -> list[list[str]]:
    """Contenido actual de la pestana (CSV descargado con la sesion del usuario)."""
    gid = config.GOOGLE_SHEET_URL.split("gid=")[1]
    url = f"https://docs.google.com/spreadsheets/d/{_id_hoja()}/export?format=csv&gid={gid}"
    # 429 = Google pide esperar (se lee la hoja muchas veces seguidas); 5xx = falla pasajera: se reintenta
    for espera in (20, 40, 60, None):
        resp = hoja.context.request.get(url)
        if resp.ok:
            return list(csv.reader(io.StringIO(resp.text())))
        if espera is None or not (resp.status == 429 or resp.status >= 500):
            break
        print(f"   (Google respondio HTTP {resp.status} al leer la hoja: se espera {espera} s y se reintenta; "
              f"no cierres nada, el bot sigue solo)")
        # Espera de Playwright (no time.sleep): la conexion con los navegadores sigue atendida mientras tanto
        hoja.wait_for_timeout(espera * 1000)
    raise RuntimeError(f"No se pudo leer la hoja (HTTP {resp.status})")


def _celda(filas, fila: int, col: str) -> str:
    """Valor de la celda (fila 1 = primera fila de la hoja)."""
    i = ord(col) - ord("A")
    return filas[fila - 1][i].strip() if fila <= len(filas) and i < len(filas[fila - 1]) else ""


def referencias(filas) -> dict[str, dict]:
    """Datos iniciales de cada usuario segun la hoja (columna A): nombre inicial (B) y direccion (E).
    Es la tercera fuente, junto al Excel y Kobo, para decidir nombre y casa cuando no coinciden."""
    refs = {}
    for n in range(FILA_ENCABEZADOS + 1, len(filas) + 1):
        numero, nombre = _celda(filas, n, COL_NUMERO), _celda(filas, n, "B")
        if numero and nombre:
            refs[numero] = {"nombre": nombre, "direccion": _celda(filas, n, COL_DIRECCION_INICIAL), "fila": n}
    return refs


def buscar_fila(filas, numero_usuario: str) -> int | None:
    """Fila de la hoja cuyo No. (columna A) es el usuario. Solo filas con nombre: al final de la hoja
    hay numeros sueltos sin datos que no cuentan."""
    encontradas = [n for n in range(FILA_ENCABEZADOS + 1, len(filas) + 1)
                   if _celda(filas, n, COL_NUMERO) == str(numero_usuario) and _celda(filas, n, "B")]
    if len(encontradas) > 1:
        raise RuntimeError(f"El usuario {numero_usuario} aparece en varias filas de la hoja: {encontradas}")
    return encontradas[0] if encontradas else None


# ---------- Valores ----------

def direccion_hoja(texto: str) -> str:
    """CS -> CASA y en el orden casa, numero, barrio.
    'UB EL TRIUNFO CS 246B DIV 1' -> 'CASA 246 B EL TRIUNFO DIV 1'. Sin 'CS' se deja igual (en mayuscula)."""
    t = " ".join(str(texto).upper().split())
    t = re.sub(r"(\d)([A-Z]{2,})", r"\1 \2", t)  # 'CS 171EL TRIUNFO' -> 'CS 171 EL TRIUNFO'
    m = re.search(r"\b(?:CS|CASA)\.?\s*(\d+)\s*([A-Z])?(?![A-Z0-9])", t)
    if m:
        casa = f"CASA {m.group(1)}" + (f" {m.group(2)}" if m.group(2) else "")
    else:
        m = re.search(r"\b(?:CS|CASA)\b\.?", t)
        if not m:
            return t
        casa = "CASA"
    resto = re.sub(r"^\s*UB\b", "", t[:m.start()] + " " + t[m.end():])
    return " ".join(f"{casa} {resto}".split())


def valores_usuario(usuario, direccion_inicial: str) -> dict[str, str]:
    """Lo que se escribe en la fila del usuario, columna -> valor, a partir del Excel de usuarios.

    F es el usuario final: el nombre de Kobo si quien atendio es otra persona (columna L del Excel).
    H parte de la direccion inicial (E) pero con la casa que quedo en el formulario 1 (columna M).
    """
    direccion = direccion_hoja(direccion_inicial)
    casa = reglas.casa_corta(getattr(usuario, "casa_final", ""))
    if casa and not (numeros_casa(casa) & numeros_casa(direccion)):
        barrio = re.sub(r"^CASA(\s+\d+(\s[A-Z](?![A-Z0-9]))?)?\s*", "", direccion)
        direccion = f"{casa} {barrio}".strip()
    valores = {
        COL_NOMBRE: " ".join((getattr(usuario, "nombre_final", "") or usuario.nombre).upper().split()),
        COL_DOCUMENTO: usuario.documento,
        COL_DIRECCION: direccion,
        COL_VERIFICACION: "CONFIRMADO" if usuario.propietario.lower() == "si" else "INCORPORADO",
        # El texto escrito en la ventana del documento (columna N); si no hubo ventana, el de siempre
        COL_SOPORTE: (getattr(usuario, "soporte", "") or
                      (reglas.SOPORTE_CON_ANEXO if usuario.anexo.lower() == "si" else reglas.SOPORTE_SIN_ANEXO)),
        COL_RESPONSABLE: RESPONSABLE,
    }
    # Observacion solo si se decidio una (columna P del Excel); si no, la columna L no se toca
    if getattr(usuario, "observacion", ""):
        valores[COL_OBSERVACION] = usuario.observacion
    return valores


# ---------- Escritura ----------

def escribir_celda(hoja: Page, celda: str, valor: str):
    """Va a la celda con el cuadro de nombre y escribe el valor como una persona."""
    caja = hoja.locator("#t-name-box")
    caja.click()
    caja.fill(f"'{PESTANA}'!{celda}")
    caja.press("Enter")
    hoja.wait_for_timeout(random.randint(250, 450))
    hoja.keyboard.type(valor, delay=random.randint(15, 35))
    # Sheets autocompleta con valores de la columna (ej. 'CEDULA DE CIUDADANIA' -> '... Y FACTURA DE ENERGIA'):
    # Supr borra la sugerencia antes de confirmar
    hoja.keyboard.press("Delete")
    hoja.keyboard.press("Enter")
    hoja.wait_for_timeout(random.randint(200, 400))


def valores_retirado(usuario, direccion_inicial: str) -> dict[str, str]:
    """Vivienda inexistente (lote vacio): la fila queda como las RETIRADO que ya habia en la hoja
    (documento 0 y soporte 'FOTOGRAFIA VIVIENDA')."""
    return {
        COL_NOMBRE: " ".join((getattr(usuario, "nombre_final", "") or usuario.nombre).upper().split()),
        COL_DOCUMENTO: "0",
        COL_DIRECCION: direccion_hoja(direccion_inicial),
        COL_VERIFICACION: "RETIRADO",
        COL_SOPORTE: "FOTOGRAFIA VIVIENDA",
        COL_RESPONSABLE: RESPONSABLE,
        COL_OBSERVACION: OBSERVACION_RETIRADO,
    }


def actualizar_usuario(hoja: Page, usuario, retirado: bool = False) -> bool:
    """Busca al usuario en la columna A y llena F a K. Devuelve True si la hoja quedo con esos valores.
    retirado=True: vivienda inexistente, la fila queda RETIRADO."""
    filas = leer_filas(hoja)
    fila = buscar_fila(filas, usuario.usuario)
    if not fila:
        print(f"   Hoja: el usuario {usuario.usuario} no esta en la columna A de '{PESTANA}'.")
        return False
    # La fila debe ser de esta persona (nombre inicial B o casa inicial E): con el No. de usuario equivocado en
    # el Excel se llenaba la fila de otra (Oleisa Cuero con el 782, que es de Johan Aguirre)
    nombres = [n for n in (usuario.nombre, getattr(usuario, "nombre_final", "")) if n]
    inicial, direccion = _celda(filas, fila, "B"), _celda(filas, fila, COL_DIRECCION_INICIAL)
    casas = numeros_casa(usuario.casa) | numeros_casa(getattr(usuario, "casa_final", ""))
    if (max(similitud_nombre(n, inicial) for n in nombres) < 0.6
            and not ({c for c, _ in casas} & {c for c, _ in numeros_casa(re.sub(r"DIV\s*\d+", "", direccion))})):
        print(f"   [!] Hoja: la fila {fila} del usuario {usuario.usuario} es de '{inicial}' ({direccion}), no de "
              f"'{usuario.nombre}' casa {usuario.casa}: revisa el No. de usuario en el Excel. No se llena.")
        return False
    faltan = [n for n, v in (("documento", usuario.documento), ("propietario", usuario.propietario),
                             ("documento anexo", usuario.anexo)) if not v]
    if faltan and not retirado:
        print(f"   Hoja: faltan datos en el Excel ({', '.join(faltan)}); no se llena la fila {fila}.")
        return False

    valores = (valores_retirado if retirado else valores_usuario)(usuario, _celda(filas, fila, COL_DIRECCION_INICIAL))
    print(f"   Hoja '{PESTANA}', fila {fila} (usuario {usuario.usuario}):")
    hoja.bring_to_front()
    for col, valor in valores.items():
        escribir_celda(hoja, f"{col}{fila}", valor)
        print(f"     {col}{fila} = {valor}")
    return verificar(hoja, fila, valores)


def _igual(columna: str, hay: str, esperado: str) -> bool:
    """El documento puede verse con puntos ('13.015.205') segun el formato de la columna: se comparan los digitos."""
    if columna == COL_DOCUMENTO:
        return re.sub(r"\D", "", hay) == re.sub(r"\D", "", esperado)
    return hay == esperado


def verificar(hoja: Page, fila: int, valores: dict[str, str], espera_s: int = 30) -> bool:
    """Relee la hoja hasta que la fila tenga los valores escritos (Google guarda en segundos)."""
    limite = time.monotonic() + espera_s
    while True:
        filas = leer_filas(hoja)
        distintos = {c: (_celda(filas, fila, c), v) for c, v in valores.items() if not _igual(c, _celda(filas, fila, c), v)}
        if not distintos:
            print("   Hoja: fila verificada, quedo con todos los valores.")
            return True
        if time.monotonic() > limite:
            for c, (hay, esperado) in distintos.items():
                print(f"   [!] {c}{fila}: dice '{hay}', se esperaba '{esperado}'")
            return False
        hoja.wait_for_timeout(3000)
