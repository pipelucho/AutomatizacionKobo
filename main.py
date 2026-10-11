from tumaco import config, correcciones, excel
from tumaco.browser import abrir_navegador
from tumaco.kobo import Kobo


def main():
    usuario = excel.siguiente_pendiente()
    if not usuario:
        print("No hay usuarios pendientes en el Excel (columna D vacia).")
        return
    print(f"Usuario a revisar: {usuario.nombre} | USUARIO {usuario.usuario} | CASA {usuario.casa} (fila {usuario.fila})")

    with abrir_navegador() as (_, page):
        kobo = Kobo(page)
        kobo.iniciar_sesion()

        # Por ahora solo el formulario 1
        kobo.abrir_formulario(config.FORMULARIOS[0])
        kobo.ir_a_datos()
        encontrado = kobo.buscar_usuario(usuario, etiqueta="form1")
        if encontrado:
            edicion = kobo.abrir_edicion(encontrado)
            print(f"Formulario de edicion abierto: {edicion.url}")

            print("\nCorrecciones del formulario 1:")
            cambios = correcciones.aplicar(edicion, 1)
            print(f"\n{len(cambios)} campo(s) corregido(s). El formulario NO se ha enviado todavia.")

        input("\nRevisa el resultado en el navegador. Presiona Enter para cerrar (sin enviar)...")


if __name__ == "__main__":
    main()
