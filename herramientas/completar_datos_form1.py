r"""Llena las columnas H (propietario), I (documento) y J (documento anexo) de quienes ya hicieron
el formulario 1 antes de que el bot guardara esos datos. Solo LEE el formulario 1 en Kobo: no corrige ni envia nada.

Uso (con el bot cerrado, comparten navegador):
    .venv\Scripts\python herramientas\completar_datos_form1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import guardar_datos_formulario  # noqa: E402
from tumaco import config, correcciones, excel  # noqa: E402
from tumaco.browser import abrir_navegador  # noqa: E402
from tumaco.kobo import Kobo  # noqa: E402


def main():
    tabla = excel.cargar_tabla()
    faltan = [
        excel.Usuario(fila=int(f.fila), nombre=f.nombre, usuario=f.usuario, casa=f.casa)
        for f in tabla.itertuples(index=False)
        if f.usuario and f.formulario1 and (not f.propietario or not f.documento or not f.anexo)
    ]
    print(f"{len(faltan)} persona(s) con el formulario 1 hecho y sin propietario/documento/anexo en el Excel.")
    if not faltan:
        return
    with abrir_navegador() as (_, page, _p):
        kobo = Kobo(page)
        kobo.iniciar_sesion()
        for usuario in faltan:
            print(f"\n{usuario.nombre} | USUARIO {usuario.usuario} (fila {usuario.fila})")
            kobo.abrir_datos(config.FORMULARIOS[0])
            encontrado = kobo.buscar_usuario(usuario, etiqueta="completar_form1")
            if not encontrado:
                print("   No se encontro en el formulario 1; se deja vacio.")
                continue
            edicion = kobo.abrir_edicion(encontrado)
            try:
                guardar_datos_formulario(edicion, usuario, 1)
                # Lo que quedo en Kobo: si hoy tiene documento anexo es porque se conservo
                anexo = correcciones.hay_documento_anexo(edicion, 1)
                if anexo:
                    excel.marcar(usuario.fila, anexo, excel.COL_ANEXO)
                    print(f"Excel: fila {usuario.fila}, columna J (documento anexo) = '{anexo}'")
            finally:
                edicion.close()  # SIN enviar
        excel.guardar_pendientes(esperar=True)


if __name__ == "__main__":
    main()
