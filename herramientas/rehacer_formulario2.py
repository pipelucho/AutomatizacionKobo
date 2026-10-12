r"""Vuelve a pasar el formulario 2 de quienes quedaron con "Revisar a mano" (cedulas sin ajustar)
y, si queda enviado, pone "Si" en la columna E y vuelve a armar su PDF unido.

Las cedulas que el bot no pueda ajustar solo te las pregunta en una ventana sobre el formulario
(usar, girar, marcar las 4 esquinas o dejar la original). Las que ya estaban ajustadas no se tocan.

Uso (con el bot cerrado y el Excel cerrado):
    .venv\Scripts\python herramientas\rehacer_formulario2.py            (solo "Revisar a mano")
    .venv\Scripts\python herramientas\rehacer_formulario2.py --todos    (todos los que ya tienen el 2)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from tumaco import excel, pdf  # noqa: E402
from tumaco.browser import abrir_navegador  # noqa: E402
from tumaco.kobo import Kobo  # noqa: E402


def a_rehacer(tabla, todos: bool) -> list[excel.Usuario]:
    usuarios = []
    for f in tabla.itertuples(index=False):
        marca = f.formulario2.strip().lower()
        if f.usuario and (marca.startswith(excel.MARCA_A_MANO.lower()) or (todos and excel.fue_enviado(marca))):
            usuarios.append(excel.Usuario(
                fila=int(f.fila), nombre=f.nombre, usuario=f.usuario, casa=f.casa,
                **{f"formulario{n}": getattr(f, f"formulario{n}") for n in excel.COLUMNA_FORMULARIO},
                **{campo: getattr(f, campo) for campo in excel.COLUMNA_DATO}))
    return usuarios


def main_rehacer():
    usuarios = a_rehacer(excel.cargar_tabla(), todos="--todos" in sys.argv)
    print(f"{len(usuarios)} persona(s) para rehacer el formulario 2.")
    if not usuarios:
        return
    listos, siguen = [], []
    with abrir_navegador() as (_, page, _p):
        kobo = Kobo(page)
        kobo.iniciar_sesion()
        for n, usuario in enumerate(usuarios, start=1):
            print("\n" + "=" * 70)
            print(f"[{n}/{len(usuarios)}] {usuario.nombre} | USUARIO {usuario.usuario} (fila {usuario.fila}) "
                  f"| antes: {usuario.formulario2}")
            print("=" * 70)
            estado, nota = main._intentar(kobo, usuario, 2)
            if estado != main.ENVIADO:
                print(f"Excel: fila {usuario.fila}, columna E sin cambios ({estado})")
                siguen.append((usuario, f"no se envio ({estado})"))
                continue
            marca = nota or excel.MARCA_REALIZADO
            excel.marcar(usuario.fila, marca, excel.COL_FORMULARIO_2)
            print(f"Excel: fila {usuario.fila}, columna E = '{marca}'")
            (siguen if nota else listos).append((usuario, nota))
            print("\nVolviendo a unir los PDF del usuario:")
            try:
                pdf.unir_pdfs(pdf.carpeta_usuario(usuario.usuario, usuario.nombre))
            except Exception as e:
                print(f"   [ERROR] No se pudo unir los PDF: {type(e).__name__}: {e}")

        print("\n" + "=" * 70)
        print(f"Formulario 2 corregido: {len(listos)} | Siguen con algo a mano: {len(siguen)}")
        for u, motivo in siguen:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} ({motivo})")
        excel.guardar_pendientes(esperar=True)
        input("\nTerminado. Presiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main_rehacer()
