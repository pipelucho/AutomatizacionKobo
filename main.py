from tumaco import config, correcciones, excel, pdf
from tumaco.browser import abrir_navegador
from tumaco.kobo import Kobo


ENVIADO, OTRO, PENDIENTE = "enviado", "otro", "pendiente"


def procesar_usuario(kobo: Kobo, usuario: excel.Usuario) -> str:
    """Revisa los formularios del usuario. Devuelve ENVIADO, OTRO o PENDIENTE."""
    # Por ahora solo el formulario 1
    kobo.abrir_datos(config.FORMULARIOS[0])
    encontrado = kobo.buscar_usuario(usuario, etiqueta="form1")
    if not encontrado:
        return PENDIENTE

    edicion = kobo.abrir_edicion(encontrado)
    try:
        print(f"Formulario de edicion abierto: {edicion.url}")

        # Si la persona que atiende la visita manifiesta ser "Otro", no se corrige ni se envia
        print("\nVerificacion del usuario (la persona que atiende la visita manifiesta ser):")
        es_otro = correcciones.marco_opcion_otro(edicion, 1)
        if es_otro is None:
            print("   No se pudo verificar la opcion 'Otro': queda pendiente para revisarlo a mano.")
            return PENDIENTE
        if es_otro:
            print("   Marco la opcion 'Otro': no se corrige ni se envia.")
            return OTRO

        print("\nCorrecciones del formulario 1:")
        cambios = correcciones.aplicar(edicion, 1, usuario)
        print(f"\n{len(cambios)} cambio(s) aplicado(s).")

        # La carpeta usa el nombre de Kobo (el del Excel puede tener errores de digitacion)
        carpeta = pdf.carpeta_usuario(usuario.usuario, encontrado.nombre or usuario.nombre)
        print(f"\nGuardando PDF en {carpeta.name}...")
        pdf.guardar_pdf(edicion, carpeta)

        print()
        enviado = kobo.enviar_edicion(edicion)
    finally:
        # Cerrar SIEMPRE la pestaña de edicion (tambien si hubo error) para no acumular pestañas.
        # Un fallo aqui no debe hacer perder un envio que Kobo ya confirmo.
        try:
            if edicion is not kobo.page and not edicion.is_closed():
                edicion.close()
            kobo.page.bring_to_front()
        except Exception as e:
            print(f"   (no se pudo cerrar la pestaña de edicion: {e})")
    print("Formulario 1 terminado." if enviado else "Formulario 1 NO se envio (el PDF si quedo guardado).")
    return ENVIADO if enviado else PENDIENTE


def main():
    # El Excel se lee una sola vez; durante la corrida solo se escribe para marcar REALIZADO
    tabla = excel.cargar_tabla()
    por_procesar = excel.pendientes(tabla)
    print(f"{config.EXCEL_PATH.name}: {len(tabla)} fila(s), {len(por_procesar)} pendiente(s) por procesar.")
    if not por_procesar:
        return

    terminados, con_otro, pendientes = [], [], []
    with abrir_navegador() as (_, page):
        kobo = Kobo(page)
        kobo.iniciar_sesion()

        for n, usuario in enumerate(por_procesar, start=1):
            print("\n" + "=" * 70)
            print(f"[{n}/{len(por_procesar)}] Usuario: {usuario.nombre} | USUARIO {usuario.usuario} "
                  f"| CASA {usuario.casa} (fila {usuario.fila})")
            print("=" * 70)
            try:
                resultado = procesar_usuario(kobo, usuario)
            except Exception as e:  # un error con un usuario no detiene a los demas
                print(f"\n[ERROR] {type(e).__name__}: {e}")
                resultado = PENDIENTE
                kobo.cerrar_pestanas_extra()  # que el siguiente usuario empiece limpio

            if resultado == ENVIADO:
                excel.marcar_realizado(usuario.fila)
                print(f"Excel: fila {usuario.fila} marcada como REALIZADO = {excel.MARCA_REALIZADO}")
                terminados.append(usuario)
            elif resultado == OTRO:
                excel.marcar(usuario.fila, excel.MARCA_OTRO)
                print(f"Excel: fila {usuario.fila} marcada como '{excel.MARCA_OTRO}'")
                con_otro.append(usuario)
            else:
                print(f"Excel: fila {usuario.fila} queda pendiente (no se completo la actualizacion)")
                pendientes.append(usuario)

        print("\n" + "=" * 70)
        print(f"Terminados: {len(terminados)} | Con opcion 'Otro': {len(con_otro)} "
              f"| Pendientes con problema: {len(pendientes)}")
        for u in con_otro:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} ({excel.MARCA_OTRO})")
        for u in pendientes:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre}")
        input("\nSe procesaron todos los pendientes. Presiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
