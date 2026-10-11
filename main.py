from tumaco import config, correcciones, excel, pdf
from tumaco.browser import abrir_navegador
from tumaco.kobo import Kobo


def procesar_usuario(kobo: Kobo, usuario: excel.Usuario) -> bool:
    """Revisa los formularios del usuario. Devuelve True solo si todo se actualizo en Kobo."""
    # Por ahora solo el formulario 1
    kobo.abrir_formulario(config.FORMULARIOS[0])
    kobo.ir_a_datos()
    encontrado = kobo.buscar_usuario(usuario, etiqueta="form1")
    if not encontrado:
        return False

    edicion = kobo.abrir_edicion(encontrado)
    print(f"Formulario de edicion abierto: {edicion.url}")

    print("\nCorrecciones del formulario 1:")
    cambios = correcciones.aplicar(edicion, 1)
    print(f"\n{len(cambios)} cambio(s) aplicado(s).")

    # La carpeta usa el nombre de Kobo (el del Excel puede tener errores de digitacion)
    carpeta = pdf.carpeta_usuario(usuario.usuario, encontrado.nombre or usuario.nombre)
    print(f"\nGuardando PDF en {carpeta.name}...")
    pdf.guardar_pdf(edicion, carpeta)

    print()
    enviado = kobo.enviar_edicion(edicion)
    if edicion is not kobo.page and not edicion.is_closed():
        edicion.close()  # cerrar la pestaña de edicion y seguir en la de Kobo
    print("Formulario 1 terminado." if enviado else "Formulario 1 NO se envio (el PDF si quedo guardado).")
    return enviado


def main():
    terminados, pendientes = [], []
    with abrir_navegador() as (_, page):
        kobo = Kobo(page)
        kobo.iniciar_sesion()

        # Un usuario tras otro hasta que no queden filas con REALIZADO (D) vacio.
        # Los que fallan en esta corrida se saltan para no repetirlos en bucle.
        while usuario := excel.siguiente_pendiente(omitir={u.fila for u in pendientes}):
            print("\n" + "=" * 70)
            print(f"Usuario: {usuario.nombre} | USUARIO {usuario.usuario} | CASA {usuario.casa} (fila {usuario.fila})")
            print("=" * 70)
            try:
                ok = procesar_usuario(kobo, usuario)
            except Exception as e:  # un error con un usuario no detiene a los demas
                print(f"\n[ERROR] {type(e).__name__}: {e}")
                ok = False

            if ok:
                excel.marcar_realizado(usuario.fila)
                print(f"Excel: fila {usuario.fila} marcada como REALIZADO = {excel.MARCA_REALIZADO}")
                terminados.append(usuario)
            else:
                print(f"Excel: fila {usuario.fila} queda pendiente (no se completo la actualizacion)")
                pendientes.append(usuario)

        print("\n" + "=" * 70)
        print(f"Terminados: {len(terminados)} | Pendientes con problema: {len(pendientes)}")
        for u in pendientes:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre}")
        input("\nNo hay mas usuarios pendientes. Presiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
