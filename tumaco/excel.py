from dataclasses import dataclass

import openpyxl
import pandas as pd

from . import config

COL_NOMBRE, COL_USUARIO, COL_CASA, COL_REALIZADO = 1, 2, 3, 4  # A, B, C, D
MARCA_REALIZADO = "Si"
MARCA_OTRO = "Tiene otro"  # la persona que atiende manifiesta ser "Otro": no se procesa


@dataclass
class Usuario:
    fila: int
    nombre: str
    usuario: str
    casa: str


def _texto(valor) -> str:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def cargar_tabla() -> pd.DataFrame:
    """Lee el Excel UNA sola vez: nombre, usuario, casa, realizado y la fila real de Excel."""
    crudo = pd.read_excel(config.EXCEL_PATH, header=0, dtype=object)
    while len(crudo.columns) < COL_REALIZADO:  # la columna REALIZADO puede no existir todavia
        crudo[f"_vacia_{len(crudo.columns)}"] = None
    tabla = pd.DataFrame({
        "nombre": crudo.iloc[:, COL_NOMBRE - 1],
        "usuario": crudo.iloc[:, COL_USUARIO - 1],
        "casa": crudo.iloc[:, COL_CASA - 1],
        "realizado": crudo.iloc[:, COL_REALIZADO - 1],
    }).map(_texto)
    tabla["fila"] = crudo.index + 2  # la fila 1 son los encabezados
    return tabla


def pendientes(tabla: pd.DataFrame) -> list[Usuario]:
    """Usuarios con USUARIO y con la columna REALIZADO (D) vacia, en el orden del Excel."""
    filtro = (tabla["usuario"] != "") & (tabla["realizado"] == "")
    return [
        Usuario(fila=int(f.fila), nombre=f.nombre, usuario=f.usuario, casa=f.casa)
        for f in tabla[filtro].itertuples(index=False)
    ]


def marcar_realizado(fila: int):
    """Marca REALIZADO apenas Kobo confirma el envio."""
    marcar(fila, MARCA_REALIZADO)


def marcar(fila: int, valor: str):
    """Escribe `valor` en la columna REALIZADO (D) de la fila (con openpyxl para conservar el formato).

    Cualquier valor en esa columna hace que la fila no se vuelva a procesar.
    """
    wb = openpyxl.load_workbook(config.EXCEL_PATH)
    ws = wb.active
    if not _texto(ws.cell(1, COL_REALIZADO).value):
        ws.cell(1, COL_REALIZADO).value = "REALIZADO:"
    ws.cell(fila, COL_REALIZADO).value = valor
    while True:
        try:
            wb.save(config.EXCEL_PATH)
            return
        except PermissionError:
            input(f"Cierra {config.EXCEL_PATH.name} en Excel y presiona Enter para guardar...")
