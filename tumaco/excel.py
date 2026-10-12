import json
from dataclasses import dataclass

import openpyxl
import pandas as pd

from . import config

COL_NOMBRE, COL_USUARIO, COL_CASA = 1, 2, 3  # A, B, C
COL_REALIZADO, COL_FORMULARIO_2, COL_FORMULARIO_3, COL_FORMULARIO_4 = 4, 5, 6, 7  # D, E, F, G
# Columna donde se marca cada formulario (numero de formulario -> columna)
COL_PROPIETARIO = 8  # H: si la persona que atiende el formulario 1 es propietaria (Si / No)
COL_DOCUMENTO = 9  # I: documento de la persona atendida segun el formulario 1
COL_ANEXO = 10  # J: si se conservo el documento anexo del formulario 1 (Si / No)
COL_HOJA = 11  # K: "Si" cuando la fila del usuario quedo llena y verificada en la hoja de Google
COL_NOMBRE_FINAL = 12  # L: nombre de quien atendio (Kobo) cuando es otra persona que la del Excel
COL_CASA_FINAL = 13  # M: casa que quedo en Kobo cuando no es la del Excel (el Excel estaba mal)
COL_SOPORTE = 14  # N: texto de soportes para la columna J de la hoja (escrito en la ventana del documento)
# Datos del formulario 1 que se guardan para usarlos despues en la hoja de Google (campo -> columna)
COLUMNA_DATO = {"propietario": COL_PROPIETARIO, "documento": COL_DOCUMENTO, "anexo": COL_ANEXO,
                "hoja": COL_HOJA, "nombre_final": COL_NOMBRE_FINAL, "casa_final": COL_CASA_FINAL,
                "soporte": COL_SOPORTE}
# Formularios que algunas personas no tienen: "No encontrado" no detiene a la persona
FORMULARIOS_OPCIONALES = {4}
COLUMNA_FORMULARIO = {1: COL_REALIZADO, 2: COL_FORMULARIO_2, 3: COL_FORMULARIO_3, 4: COL_FORMULARIO_4}
ENCABEZADOS = {COL_REALIZADO: "REALIZADO:", COL_FORMULARIO_2: "FORMULARIO 2:", COL_FORMULARIO_3: "FORMULARIO 3:",
              COL_FORMULARIO_4: "FORMULARIO 4:", COL_PROPIETARIO: "PROPIETARIO:",
              COL_DOCUMENTO: "DOCUMENTO:", COL_ANEXO: "DOCUMENTO ANEXO:", COL_HOJA: "HOJA:",
              COL_NOMBRE_FINAL: "NOMBRE FINAL:", COL_CASA_FINAL: "CASA FINAL:",
              COL_SOPORTE: "SOPORTES HOJA:"}
MARCA_REALIZADO = "Si"
MARCA_A_MANO = "Revisar a mano"  # se envio, pero algo quedo para hacerlo a mano (ej. una cedula)
MARCA_NO_ENCONTRADO = "No encontrado"  # formulario que no existe para esa persona (ej. el 4)
MARCA_OTRO = "Tiene otro"  # la persona que atiende manifiesta ser "Otro": no se procesa
# Marcas que no se pudieron escribir porque el Excel estaba abierto: [fila, columna, valor]
PENDIENTES_PATH = config.OUTPUT_DIR / "marcas_pendientes.json"


@dataclass
class Usuario:
    fila: int
    nombre: str
    usuario: str
    casa: str
    formulario1: str = ""  # valor de la columna D
    formulario2: str = ""  # valor de la columna E
    formulario3: str = ""  # valor de la columna F
    formulario4: str = ""  # valor de la columna G
    propietario: str = ""  # columna H
    documento: str = ""  # columna I
    anexo: str = ""  # columna J
    hoja: str = ""  # columna K
    nombre_final: str = ""  # columna L
    casa_final: str = ""  # columna M
    soporte: str = ""  # columna N
    # Datos iniciales del usuario en la hoja de Google (no se guardan en el Excel)
    ref_nombre: str = ""
    ref_direccion: str = ""

    def marca(self, numero: int) -> str:
        """Lo que dice el Excel para el formulario `numero` (vacio = falta hacerlo)."""
        return getattr(self, f"formulario{numero}", "").strip()

    def siguiente(self) -> int | None:
        """Primer formulario por hacer, o None si ya termino o una marca detiene la cadena
        (ej. 'Tiene otro' o 'No encontrado' en un formulario anterior)."""
        for numero in sorted(COLUMNA_FORMULARIO):
            marca = self.marca(numero)
            if not marca:
                return numero
            if not fue_enviado(marca):
                return None
        return None


    def terminado(self) -> bool:
        """Todos los formularios enviados (uno opcional como el 4 puede ser 'No encontrado')."""
        for numero in sorted(COLUMNA_FORMULARIO):
            marca = self.marca(numero)
            opcional_sin_formulario = (numero in FORMULARIOS_OPCIONALES
                                       and marca.lower() == MARCA_NO_ENCONTRADO.lower())
            if not (fue_enviado(marca) or opcional_sin_formulario):
                return False
        return True


def fue_enviado(marca: str) -> bool:
    """La marca indica que el formulario quedo enviado ('Si', o 'Revisar a mano: ...')."""
    m = marca.strip().lower()
    return m == MARCA_REALIZADO.lower() or m.startswith(MARCA_A_MANO.lower())


def letra(columna: int) -> str:
    return chr(ord("A") + columna - 1)


def _texto(valor) -> str:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def cargar_tabla() -> pd.DataFrame:
    """Lee el Excel UNA sola vez: nombre, usuario, casa, marcas de cada formulario y la fila real de Excel."""
    # Primero las marcas de una corrida anterior en la que el Excel estaba abierto, y DESPUES se lee:
    # leyendo antes, la tabla no las veia (se saltaba o repetia personas)
    guardar_pendientes()
    crudo = pd.read_excel(config.EXCEL_PATH, header=0, dtype=object)
    while len(crudo.columns) < max(*COLUMNA_FORMULARIO.values(), *COLUMNA_DATO.values()):  # D a I pueden no existir
        crudo[f"_vacia_{len(crudo.columns)}"] = None
    tabla = pd.DataFrame({
        "nombre": crudo.iloc[:, COL_NOMBRE - 1],
        "usuario": crudo.iloc[:, COL_USUARIO - 1],
        "casa": crudo.iloc[:, COL_CASA - 1],
        **{f"formulario{n}": crudo.iloc[:, col - 1] for n, col in COLUMNA_FORMULARIO.items()},
        **{campo: crudo.iloc[:, col - 1] for campo, col in COLUMNA_DATO.items()},
    }).map(_texto)
    tabla["fila"] = crudo.index + 2  # la fila 1 son los encabezados
    return aplicar_pendientes(tabla)  # las que siguen sin guardar (Excel abierto) tambien cuentan


def pendientes(tabla: pd.DataFrame) -> list[Usuario]:
    """Usuarios con algo por hacer, en el orden del Excel: tienen un formulario sin marca y todos
    los anteriores enviados, o ya terminaron los formularios y falta llenar su fila en la hoja de Google.
    Una marca como 'Tiene otro' o 'No encontrado' detiene a esa persona.
    """
    return [u for u in usuarios(tabla) if u.siguiente() is not None or (u.terminado() and not u.hoja)]


def usuarios(tabla: pd.DataFrame) -> list[Usuario]:
    """Todas las personas del Excel (con No. de usuario), con sus marcas y datos."""
    return [
        Usuario(fila=int(f.fila), nombre=f.nombre, usuario=f.usuario, casa=f.casa,
                **{f"formulario{n}": getattr(f, f"formulario{n}") for n in COLUMNA_FORMULARIO},
                **{campo: getattr(f, campo) for campo in COLUMNA_DATO})
        for f in tabla[tabla["usuario"] != ""].itertuples(index=False)
    ]


def marcar_realizado(fila: int):
    """Marca el formulario 1 (columna D) apenas Kobo confirma el envio."""
    marcar(fila, MARCA_REALIZADO)


def marcar(fila: int, valor: str, columna: int = COL_REALIZADO) -> bool:
    """Escribe `valor` en la columna indicada de la fila (con openpyxl para conservar el formato).

    Cualquier valor en D hace que el formulario 1 no se repita; en E, el formulario 2.
    Si el Excel esta abierto no se detiene la corrida: la marca queda en marcas_pendientes.json
    y se escribe en el siguiente intento (o al final, o en la proxima corrida).
    """
    marcas = _leer_pendientes()
    marcas.append([fila, columna, valor])
    _guardar_pendientes(marcas)
    return guardar_pendientes()


def guardar_pendientes(esperar: bool = False) -> bool:
    """Escribe en el Excel las marcas que no se pudieron guardar. True si ya no queda ninguna.

    Con esperar=True (al terminar la corrida) pide cerrar el Excel hasta poder guardar.
    """
    marcas = _leer_pendientes()
    if not marcas:
        return True
    while True:
        try:
            wb = openpyxl.load_workbook(config.EXCEL_PATH)
            ws = wb.active
            for fila, columna, valor in marcas:
                if not _texto(ws.cell(1, columna).value) and columna in ENCABEZADOS:
                    ws.cell(1, columna).value = ENCABEZADOS[columna]
                ws.cell(fila, columna).value = valor
            wb.save(config.EXCEL_PATH)
            PENDIENTES_PATH.unlink(missing_ok=True)
            if len(marcas) > 1:
                print(f"   Excel: se guardaron {len(marcas)} marca(s) que estaban pendientes.")
            return True
        except PermissionError:
            if not esperar:
                print(f"   [!] {config.EXCEL_PATH.name} esta abierto en Excel: la marca queda guardada en "
                      f"{PENDIENTES_PATH.name} y se escribira cuando lo cierres. Se continua.")
                return False
            input(f"Cierra {config.EXCEL_PATH.name} en Excel y presiona Enter para guardar "
                  f"{len(marcas)} marca(s) pendiente(s)...")


def aplicar_pendientes(tabla: pd.DataFrame) -> pd.DataFrame:
    """Pone en la tabla leida las marcas que aun no llegaron al Excel (para no repetir formularios)."""
    campo = {col: f"formulario{n}" for n, col in COLUMNA_FORMULARIO.items()}
    campo.update({col: nombre for nombre, col in COLUMNA_DATO.items()})
    for fila, columna, valor in _leer_pendientes():
        if columna in campo:
            tabla.loc[tabla["fila"] == fila, campo[columna]] = valor
    return tabla


def _leer_pendientes() -> list:
    try:
        return json.loads(PENDIENTES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def _guardar_pendientes(marcas: list):
    PENDIENTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDIENTES_PATH.write_text(json.dumps(marcas), encoding="utf-8")
