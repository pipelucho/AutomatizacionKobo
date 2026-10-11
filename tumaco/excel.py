from dataclasses import dataclass

import openpyxl

from . import config

COL_NOMBRE, COL_USUARIO, COL_CASA, COL_REALIZADO = 1, 2, 3, 4  # A, B, C, D
MARCA_REALIZADO = "Si"


@dataclass
class Usuario:
    fila: int
    nombre: str
    usuario: str
    casa: str


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def siguiente_pendiente(omitir: set[int] = frozenset()) -> Usuario | None:
    """Primer usuario con la columna REALIZADO (D) vacia, sin contar las filas en `omitir`."""
    ws = openpyxl.load_workbook(config.EXCEL_PATH).active
    for fila in range(2, ws.max_row + 1):
        if fila in omitir:
            continue
        usuario = _texto(ws.cell(fila, COL_USUARIO).value)
        if usuario and not _texto(ws.cell(fila, COL_REALIZADO).value):
            return Usuario(
                fila=fila,
                nombre=_texto(ws.cell(fila, COL_NOMBRE).value),
                usuario=usuario,
                casa=_texto(ws.cell(fila, COL_CASA).value),
            )
    return None


def marcar_realizado(fila: int):
    wb = openpyxl.load_workbook(config.EXCEL_PATH)
    ws = wb.active
    if not _texto(ws.cell(1, COL_REALIZADO).value):
        ws.cell(1, COL_REALIZADO).value = "REALIZADO:"
    ws.cell(fila, COL_REALIZADO).value = MARCA_REALIZADO
    while True:
        try:
            wb.save(config.EXCEL_PATH)
            return
        except PermissionError:
            input(f"Cierra {config.EXCEL_PATH.name} en Excel y presiona Enter para guardar...")
