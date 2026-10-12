"""Copia todo lo que el bot muestra en la terminal a un archivo, para revisarlo despues de cerrarla."""
import atexit
import sys
from datetime import datetime
from pathlib import Path

from . import config

LOGS_DIR = config.OUTPUT_DIR / "logs"


class _Duplicar:
    """Escribe en la terminal y en el archivo a la vez."""

    def __init__(self, terminal, archivo):
        self.terminal = terminal
        self.archivo = archivo

    def write(self, texto):
        self.terminal.write(texto)
        self.archivo.write(texto)
        self.archivo.flush()  # que quede guardado aunque se corte la corrida

    def flush(self):
        self.terminal.flush()
        self.archivo.flush()

    def __getattr__(self, nombre):  # encoding, isatty, etc. de la terminal
        return getattr(self.terminal, nombre)


def iniciar(nombre: str = "corrida") -> Path:
    """Empieza a guardar la salida en salida/logs/<nombre>_AAAA-MM-DD_HH-MM.log y devuelve la ruta."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = LOGS_DIR / f"{nombre}_{datetime.now():%Y-%m-%d_%H-%M}.log"
    archivo = open(ruta, "a", encoding="utf-8")
    terminal_out, terminal_err = sys.stdout, sys.stderr
    sys.stdout = _Duplicar(terminal_out, archivo)
    sys.stderr = _Duplicar(terminal_err, archivo)

    def cerrar():
        sys.stdout, sys.stderr = terminal_out, terminal_err
        archivo.close()

    atexit.register(cerrar)
    print(f"(Registro de esta corrida: {ruta})")
    return ruta
