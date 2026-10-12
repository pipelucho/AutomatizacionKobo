from tumaco import config, correcciones, excel, pdf
from tumaco.browser import abrir_navegador
from tumaco.kobo import Kobo


ENVIADO, OTRO, PENDIENTE, NO_ENCONTRADO = "enviado", "otro", "pendiente", "no encontrado"


def procesar_formulario(kobo: Kobo, usuario: excel.Usuario, numero: int) -> str:
    """Busca al usuario en el formulario `numero`, lo corrige, guarda el PDF y lo envia.

    Devuelve ENVIADO, OTRO (solo formulario 1), NO_ENCONTRADO (el motivo queda en kobo.motivo)
    o PENDIENTE.
    """
    kobo.abrir_datos(config.FORMULARIOS[numero - 1])
    encontrado = kobo.buscar_usuario(usuario, etiqueta=f"form{numero}")
    if not encontrado:
        return NO_ENCONTRADO

    edicion = kobo.abrir_edicion(encontrado)
    enviado = False
    try:
        print(f"Formulario de edicion abierto: {edicion.url}")
        correcciones.inventario_campos(edicion, numero)

        # Si la persona que atiende la visita manifiesta ser "Otro", no se corrige ni se envia
        if numero in correcciones.OPCION_OTRO:
            print("\nVerificacion del usuario (la persona que atiende la visita manifiesta ser):")
            es_otro = correcciones.marco_opcion_otro(edicion, numero)
            if es_otro is None:
                print("   No se pudo verificar la opcion 'Otro': queda pendiente para revisarlo a mano.")
                return PENDIENTE
            if es_otro:
                print("   Marco la opcion 'Otro': no se corrige ni se envia.")
                return OTRO

        # Un formulario sin correcciones configuradas no se envia: se marcaria como hecho sin corregirlo
        if not correcciones.tiene_correcciones(numero):
            print(f"\nEl formulario {numero} aun no tiene correcciones configuradas: no se envia.")
            print("   Revisa el inventario de campos para indicar que se debe corregir.")
            return PENDIENTE

        print(f"\nCorrecciones del formulario {numero}:")
        cambios = correcciones.aplicar(edicion, numero, usuario)
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
    print(f"Formulario {numero} terminado." if enviado
          else f"Formulario {numero} NO se envio (el PDF si quedo guardado).")
    return ENVIADO if enviado else PENDIENTE


def _intentar(kobo: Kobo, usuario: excel.Usuario, numero: int) -> str:
    """Un error con un usuario no detiene a los demas."""
    print(f"\n--- Formulario {numero}: {config.FORMULARIOS[numero - 1]} ---")
    try:
        return procesar_formulario(kobo, usuario, numero)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        kobo.cerrar_pestanas_extra()  # que lo siguiente empiece limpio
        return PENDIENTE


def main():
    # El Excel se lee una sola vez; durante la corrida solo se escribe para marcar las columnas D y E
    tabla = excel.cargar_tabla()
    por_procesar = excel.pendientes(tabla)
    print(f"{config.EXCEL_PATH.name}: {len(tabla)} fila(s), {len(por_procesar)} con formularios pendientes.")
    if not por_procesar:
        return

    terminados, con_otro, pendientes, no_encontrados = [], [], [], []
    with abrir_navegador() as (_, page):
        kobo = Kobo(page)
        kobo.iniciar_sesion()

        for n, usuario in enumerate(por_procesar, start=1):
            print("\n" + "=" * 70)
            print(f"[{n}/{len(por_procesar)}] Usuario: {usuario.nombre} | USUARIO {usuario.usuario} "
                  f"| CASA {usuario.casa} (fila {usuario.fila})")
            print("=" * 70)

            # Formulario 1 -> columna D
            if usuario.formulario1_listo:
                print("Formulario 1 ya estaba realizado (columna D): se continua con el formulario 2.")
            else:
                resultado = _intentar(kobo, usuario, 1)
                if resultado == OTRO:
                    excel.marcar(usuario.fila, excel.MARCA_OTRO)
                    print(f"Excel: fila {usuario.fila}, columna D = '{excel.MARCA_OTRO}'")
                    con_otro.append(usuario)
                    continue
                if resultado == NO_ENCONTRADO:
                    excel.marcar(usuario.fila, kobo.motivo)
                    print(f"Excel: fila {usuario.fila}, columna D = '{kobo.motivo}'")
                    no_encontrados.append((usuario, 1, kobo.motivo))
                    continue
                if resultado != ENVIADO:
                    print(f"Excel: fila {usuario.fila} queda pendiente (formulario 1 no se completo)")
                    pendientes.append((usuario, 1))
                    continue
                excel.marcar(usuario.fila, excel.MARCA_REALIZADO)
                print(f"Excel: fila {usuario.fila}, columna D = {excel.MARCA_REALIZADO}")

            # Formulario 2 -> columna E (solo si el formulario 1 quedo enviado)
            resultado = _intentar(kobo, usuario, 2)
            if resultado == ENVIADO:
                excel.marcar(usuario.fila, excel.MARCA_REALIZADO, excel.COL_FORMULARIO_2)
                print(f"Excel: fila {usuario.fila}, columna E = {excel.MARCA_REALIZADO}")
                terminados.append(usuario)
            elif resultado == NO_ENCONTRADO:
                excel.marcar(usuario.fila, kobo.motivo, excel.COL_FORMULARIO_2)
                print(f"Excel: fila {usuario.fila}, columna E = '{kobo.motivo}'")
                no_encontrados.append((usuario, 2, kobo.motivo))
            else:
                print(f"Excel: fila {usuario.fila}, formulario 2 queda pendiente (columna E vacia)")
                pendientes.append((usuario, 2))

        print("\n" + "=" * 70)
        print(f"Con formularios 1 y 2 terminados: {len(terminados)} | Con opcion 'Otro': {len(con_otro)} "
              f"| No encontrados o dudosos: {len(no_encontrados)} | Pendientes: {len(pendientes)}")
        for u in con_otro:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} ({excel.MARCA_OTRO})")
        for u, numero, motivo in no_encontrados:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (formulario {numero}: {motivo})")
        for u, numero in pendientes:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (falta formulario {numero})")
        excel.guardar_pendientes(esperar=True)  # lo que no se pudo guardar con el Excel abierto
        input("\nSe procesaron todos los pendientes. Presiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
