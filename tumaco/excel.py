import json
from dataclasses import dataclass

import openpyxl
import pandas as pd

from . import config

COL_NOMBRE, COL_USUARIO, COL_CASA = 1, 2, 3  # A, B, C
COL_REALIZADO, COL_FORMULARIO_2 = 4, 5  # D = formulario 1, E = formulario 2
ENCABEZADOS = {COL_REALIZADO: "REALIZADO:", COL_FORMULARIO_2: "FORMULARIO 2:"}
MARCA_REALIZADO = "Si"
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

    @property
    def formulario1_listo(self) -> bool:
        return self.formulario1.strip().lower() == MARCA_REALIZADO.lower()


def _texto(valor) -> str:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def cargar_tabla() -> pd.DataFrame:
    """Lee el Excel UNA sola vez: nombre, usuario, casa, columnas D y E, y la fila real de Excel."""
    crudo = pd.read_excel(config.EXCEL_PATH, header=0, dtype=object)
    while len(crudo.columns) < COL_FORMULARIO_2:  # las columnas D/E pueden no existir todavia
        crudo[f"_vacia_{len(crudo.columns)}"] = None
    tabla = pd.DataFrame({
        "nombre": crudo.iloc[:, COL_NOMBRE - 1],
        "usuario": crudo.iloc[:, COL_USUARIO - 1],
        "casa": crudo.iloc[:, COL_CASA - 1],
        "formulario1": crudo.iloc[:, COL_REALIZADO - 1],
        "formulario2": crudo.iloc[:, COL_FORMULARIO_2 - 1],
    }).map(_texto)
    tabla["fila"] = crudo.index + 2  # la fila 1 son los encabezados
    guardar_pendientes()  # marcas de una corrida anterior en la que el Excel estaba abierto
    return aplicar_pendientes(tabla)


def pendientes(tabla: pd.DataFrame) -> list[Usuario]:
    """Usuarios con algo por hacer, en el orden del Excel:
    - formulario 1 sin marca en D, o
    - formulario 1 enviado (D = Si) y formulario 2 sin marca en E.
    Una fila con D = 'Tiene otro' no se procesa.
    """
    d_vacia = tabla["formulario1"] == ""
    d_lista = tabla["formulario1"].str.lower() == MARCA_REALIZADO.lower()
    e_vacia = tabla["formulario2"] == ""
    filtro = (tabla["usuario"] != "") & (d_vacia | (d_lista & e_vacia))
    return [
        Usuario(fila=int(f.fila), nombre=f.nombre, usuario=f.usuario, casa=f.casa,
                formulario1=f.formulario1, formulario2=f.formulario2)
        for f in tabla[filtro].itertuples(index=False)
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
    campo = {COL_REALIZADO: "formulario1", COL_FORMULARIO_2: "formulario2"}
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
