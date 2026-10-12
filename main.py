import sys
import time

from tumaco import casos, config, correcciones, excel, pdf, registro, sheets
from tumaco.browser import abrir_navegador
from tumaco.kobo import Kobo


ENVIADO, OTRO, PENDIENTE, NO_ENCONTRADO = "enviado", "otro", "pendiente", "no encontrado"
# Formularios que algunas personas no tienen: si no aparece se marca "No encontrado" y se da por terminado
FORMULARIOS_OPCIONALES = excel.FORMULARIOS_OPCIONALES


class Tiempos:
    """Cuanto tarda cada paso (se muestra al final de cada formulario para encontrar demoras)."""

    def __init__(self):
        self._ultimo = time.monotonic()
        self._pasos = []

    def marcar(self, paso: str):
        ahora = time.monotonic()
        self._pasos.append((paso, ahora - self._ultimo))
        self._ultimo = ahora

    def __str__(self):
        total = sum(s for _, s in self._pasos)
        return " | ".join(f"{p} {s:.0f}s" for p, s in self._pasos) + f" | total {total:.0f}s"


def guardar_datos_formulario(edicion, usuario: excel.Usuario, numero: int):
    """Guarda en el Excel los datos del formulario que luego se usan en la hoja de Google:
    H = si quien atiende es propietario(a), I = documento. Se anotan apenas se abre el formulario,
    aunque luego no se envie (ej. opcion "Otro")."""
    propietario = correcciones.es_propietario(edicion, numero)
    if propietario:
        marca, opcion = propietario
        excel.marcar(usuario.fila, marca, excel.COL_PROPIETARIO)
        usuario.propietario = marca
        print(f"Excel: fila {usuario.fila}, columna {excel.letra(excel.COL_PROPIETARIO)} (propietario) = "
              f"'{marca}'" + (f" ({opcion})" if opcion else ""))
    documento = correcciones.leer_documento(edicion, numero)
    if documento is not None:
        excel.marcar(usuario.fila, documento, excel.COL_DOCUMENTO)
        usuario.documento = documento
        print(f"Excel: fila {usuario.fila}, columna {excel.letra(excel.COL_DOCUMENTO)} (documento) = "
              f"'{documento or 'vacio'}'")


def llenar_hoja(hoja: sheets.Hoja, usuario: excel.Usuario) -> bool:
    """Ultimo paso de cada persona: su fila en la hoja de Google (F a K). Marca la columna K del Excel."""
    print("\nHoja de Google:")
    try:
        ok = sheets.actualizar_usuario(hoja.pestana(), usuario)
    except Exception as e:  # sin la ventana de la hoja no se detiene la corrida
        print(f"   [!] {e}")
        ok = False
    if ok:
        excel.marcar(usuario.fila, excel.MARCA_REALIZADO, excel.COL_HOJA)
        usuario.hoja = excel.MARCA_REALIZADO
        print(f"Excel: fila {usuario.fila}, columna {excel.letra(excel.COL_HOJA)} (hoja) = '{excel.MARCA_REALIZADO}'")
    else:
        print("   La hoja queda pendiente para la proxima corrida.")
    return ok


def guardar_decisiones(usuario: excel.Usuario, numero: int, resultado):
    """Lo que se decidio con Kobo, el Excel y la hoja (ya enviado): avisos para verificar en CASOS.xlsx y,
    del formulario 1, el nombre de quien atendio si es otra persona (L) y la casa que quedo (M)."""
    for tipo, texto in resultado.avisos:
        casos.anotar_aviso(usuario, numero, tipo, texto)
    if numero != 1:
        return
    for campo, columna, valor in (("nombre_final", excel.COL_NOMBRE_FINAL, resultado.nombre_final),
                                  ("casa_final", excel.COL_CASA_FINAL, resultado.casa_final)):
        if valor and valor != getattr(usuario, campo):
            excel.marcar(usuario.fila, valor, columna)
            setattr(usuario, campo, valor)
            print(f"Excel: fila {usuario.fila}, columna {excel.letra(columna)} ({campo.replace('_', ' ')}) = '{valor}'")


def cargar_referencias(hoja: sheets.Hoja, usuarios: list[excel.Usuario]):
    """Nombre y direccion iniciales de cada usuario segun la hoja de Google, para decidir nombre y casa."""
    try:
        refs = sheets.referencias(sheets.leer_filas(hoja.pestana()))
    except Exception as e:
        print(f"[!] No se pudo leer la hoja de Google ({e}).\n"
              f"    Sin ella, el bot no cambia nombres ni casas que no coincidan: los deja y avisa.")
        return
    for u in usuarios:
        ref = refs.get(u.usuario, {})
        u.ref_nombre, u.ref_direccion = ref.get("nombre", ""), ref.get("direccion", "")
    print(f"Hoja de Google: datos iniciales de {sum(1 for u in usuarios if u.ref_nombre)} de {len(usuarios)} "
          f"usuario(s) para comparar nombre y casa.")


def procesar_formulario(kobo: Kobo, usuario: excel.Usuario, numero: int) -> tuple[str, str]:
    """Busca al usuario en el formulario `numero`, lo corrige, guarda el PDF y lo envia.

    Devuelve (estado, nota). Estado: ENVIADO, OTRO (solo formulario 1), NO_ENCONTRADO (el motivo
    queda en kobo.motivo) o PENDIENTE. La nota dice que quedo para hacer a mano (ej. una cedula
    que no se pudo enderezar); el resto de correcciones si se envian.
    """
    t = Tiempos()
    kobo.abrir_datos(config.FORMULARIOS[numero - 1])
    t.marcar("abrir datos")
    decidido = usuario.registro_decidido(numero)  # columna O: registro ya revisado, sin buscar ni preguntar
    encontrado = (kobo.registro_por_id(decidido) if decidido
                  else kobo.buscar_usuario(usuario, etiqueta=f"form{numero}"))
    t.marcar("buscar")
    if not encontrado:
        return NO_ENCONTRADO, ""

    edicion = kobo.abrir_edicion(encontrado)
    t.marcar("abrir edicion")
    enviado, nota = False, ""
    try:
        print(f"Formulario de edicion abierto: {edicion.url}")
        correcciones.inventario_campos(edicion, numero)

        guardar_datos_formulario(edicion, usuario, numero)

        # Si la persona que atiende la visita manifiesta ser "Otro", no se corrige ni se envia
        if numero in correcciones.OPCION_OTRO:
            print("\nVerificacion del usuario (la persona que atiende la visita manifiesta ser):")
            es_otro = correcciones.marco_opcion_otro(edicion, numero)
            if es_otro is None:
                print("   No se pudo verificar la opcion 'Otro': queda pendiente para revisarlo a mano.")
                return PENDIENTE, ""
            if es_otro:
                if not correcciones.procesar_aunque_otro(edicion, numero, usuario):
                    print("   Marco la opcion 'Otro': no se corrige ni se envia (Tiene otro).")
                    return OTRO, ""
                print("   - Opcion 'Otro': decidido en la ventana -> se procesa igual")

        # Un formulario sin correcciones configuradas no se envia: se marcaria como hecho sin corregirlo
        if not correcciones.tiene_correcciones(numero):
            print(f"\nEl formulario {numero} aun no tiene correcciones configuradas: no se envia.")
            print("   Revisa el inventario de campos para indicar que se debe corregir.")
            return PENDIENTE, ""

        print(f"\nCorrecciones del formulario {numero}:")
        # La firma que tiene hoy el registro: si ya es la del bot y esta completa no se vuelve a firmar
        firma_actual = (kobo.firma_actual(encontrado, correcciones.FIRMAS[numero]["xpath"])
                        if numero in correcciones.FIRMAS else None)
        resultado = correcciones.aplicar(edicion, numero, usuario, firma_actual)
        t.marcar("correcciones")
        print(f"\n{len(resultado.cambios)} cambio(s) aplicado(s).")
        if resultado.revisar:
            nota = "Revisar a mano: " + "; ".join(resultado.revisar)
            print(nota)

        # Carpeta con el nombre del Excel, o con el de quien atendio si es otra persona (decidido en el
        # formulario 1): asi todos los PDF de la persona quedan juntos y con el nombre de sus documentos
        carpeta = pdf.carpeta_persona(usuario, resultado.nombre_final if numero == 1 else "")
        # Orden: primero todo lo de las cedulas (ya ajustadas y cargadas), luego el PDF y al final el envio
        if {"cara", "reverso"} <= resultado.cedulas.keys():
            print(f"\nGuardando DOCUMENTO.pdf en {carpeta.name}...")
            pdf.guardar_documento(carpeta, resultado.cedulas["cara"], resultado.cedulas["reverso"])
        print(f"\nGuardando PDF en {carpeta.name}...")
        pdf.guardar_pdf(edicion, carpeta)
        t.marcar("PDF")

        print()
        enviado = kobo.enviar_edicion(edicion)
        t.marcar("envio")
        if enviado:
            guardar_decisiones(usuario, numero, resultado)
        # Columna J: solo si quedo enviado, para que coincida con lo que quedo en Kobo
        if enviado and resultado.anexo:
            excel.marcar(usuario.fila, resultado.anexo, excel.COL_ANEXO)
            usuario.anexo = resultado.anexo
            print(f"Excel: fila {usuario.fila}, columna {excel.letra(excel.COL_ANEXO)} (documento anexo) = "
                  f"'{resultado.anexo}'")
        if enviado and resultado.soporte:  # texto de la ventana del documento, para la columna J de la hoja
            excel.marcar(usuario.fila, resultado.soporte, excel.COL_SOPORTE)
            usuario.soporte = resultado.soporte
            print(f"Excel: fila {usuario.fila}, columna {excel.letra(excel.COL_SOPORTE)} (soportes hoja) = "
                  f"'{resultado.soporte}'")
    finally:
        # Cerrar SIEMPRE la pestaña de edicion (tambien si hubo error) para no acumular pestañas.
        # Un fallo aqui no debe hacer perder un envio que Kobo ya confirmo.
        try:
            if edicion is not kobo.page and not edicion.is_closed():
                edicion.close()
            kobo.page.bring_to_front()
        except Exception as e:
            print(f"   (no se pudo cerrar la pestaña de edicion: {e})")
        t.marcar("cerrar")
        print(f"   Tiempos: {t}")
    print(f"Formulario {numero} terminado." if enviado
          else f"Formulario {numero} NO se envio (el PDF si quedo guardado).")
    return (ENVIADO if enviado else PENDIENTE), nota


def _intentar(kobo: Kobo, usuario: excel.Usuario, numero: int) -> tuple[str, str]:
    """Un error con un usuario no detiene a los demas."""
    print(f"\n--- Formulario {numero}: {config.FORMULARIOS[numero - 1]} ---")
    try:
        return procesar_formulario(kobo, usuario, numero)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        casos.anotar_error(usuario, numero, f"{type(e).__name__}: {e}")  # queda en CASOS.xlsx
        kobo.cerrar_pestanas_extra()  # que lo siguiente empiece limpio
        return PENDIENTE, ""


def _limite() -> int | None:
    """Numero de personas de '--limite N' en la linea de comando (None = todas)."""
    if "--limite" in sys.argv:
        i = sys.argv.index("--limite")
        if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            return int(sys.argv[i + 1])
    return None


def actualizar_casos():
    """Al final de la corrida: CASOS.xlsx con lo que quedo por resolver (relee el Excel ya marcado)."""
    print("\nRegistro de casos:")
    filas = casos.actualizar(excel.cargar_tabla())
    if filas is not None:
        print(f"   {casos.resumen(filas)}")


def main():
    registro.iniciar("corrida")  # todo lo que se ve en la terminal queda tambien en salida/logs
    # El Excel se lee una sola vez; durante la corrida solo se escribe para marcar cada formulario
    tabla = excel.cargar_tabla()
    por_procesar = excel.pendientes(tabla)
    print(f"{config.EXCEL_PATH.name}: {len(tabla)} fila(s), {len(por_procesar)} con formularios pendientes.")
    if limite := _limite():  # ej. main.py --limite 5: una prueba con pocas personas
        por_procesar = por_procesar[:limite]
        print(f"Prueba: solo las primeras {len(por_procesar)}: "
              + ", ".join(f"{u.usuario} {u.nombre}" for u in por_procesar))
    if not por_procesar:
        actualizar_casos()
        return

    terminados, con_otro, pendientes, no_encontrados, a_mano = [], [], [], [], []
    sin_formulario = []  # (usuario, numero) de formularios opcionales que no existen para esa persona
    sin_configurar = set()  # formularios sin correcciones cuyo inventario ya se guardo en esta corrida
    hoja_pendiente = []  # personas terminadas cuya fila en la hoja de Google no se pudo llenar
    with abrir_navegador() as (_, page, playwright):
        kobo = Kobo(page)
        kobo.iniciar_sesion()
        hoja = sheets.Hoja(playwright)
        cargar_referencias(hoja, por_procesar)

        for n, usuario in enumerate(por_procesar, start=1):
            print("\n" + "=" * 70)
            print(f"[{n}/{len(por_procesar)}] Usuario: {usuario.nombre} | USUARIO {usuario.usuario} "
                  f"| CASA {usuario.casa} (fila {usuario.fila})")
            print("=" * 70)

            # Formularios en orden; cada uno solo si el anterior quedo enviado
            for numero, columna in sorted(excel.COLUMNA_FORMULARIO.items()):
                letra = excel.letra(columna)
                marca = usuario.marca(numero)
                if marca:
                    if excel.fue_enviado(marca):
                        print(f"Formulario {numero} ya estaba realizado (columna {letra}).")
                        continue
                    print(f"Formulario {numero} tiene '{marca}' en la columna {letra}: no se sigue con esta persona.")
                    break
                if numero in sin_configurar:
                    print(f"Formulario {numero} aun sin correcciones configuradas: se salta "
                          f"(su inventario de campos ya se guardo en esta corrida).")
                    pendientes.append((usuario, numero))
                    break

                resultado, nota = _intentar(kobo, usuario, numero)
                if not correcciones.tiene_correcciones(numero):
                    sin_configurar.add(numero)
                if resultado == OTRO:
                    excel.marcar(usuario.fila, excel.MARCA_OTRO, columna)
                    print(f"Excel: fila {usuario.fila}, columna {letra} = '{excel.MARCA_OTRO}'")
                    con_otro.append(usuario)
                    break
                if resultado == NO_ENCONTRADO and numero in FORMULARIOS_OPCIONALES \
                        and kobo.motivo.startswith(excel.MARCA_NO_ENCONTRADO):
                    # Hay personas sin este formulario: se anota y la persona queda terminada
                    excel.marcar(usuario.fila, excel.MARCA_NO_ENCONTRADO, columna)
                    print(f"Excel: fila {usuario.fila}, columna {letra} = '{excel.MARCA_NO_ENCONTRADO}'")
                    sin_formulario.append((usuario, numero))
                    continue
                if resultado == NO_ENCONTRADO:
                    excel.marcar(usuario.fila, kobo.motivo, columna)
                    print(f"Excel: fila {usuario.fila}, columna {letra} = '{kobo.motivo}'")
                    no_encontrados.append((usuario, numero, kobo.motivo))
                    break
                if resultado != ENVIADO:
                    print(f"Excel: fila {usuario.fila}, formulario {numero} queda pendiente (columna {letra} vacia)")
                    pendientes.append((usuario, numero))
                    break
                # Enviado. Si algo quedo para hacer a mano (ej. una cedula), se anota en vez de "Si"
                excel.marcar(usuario.fila, nota or excel.MARCA_REALIZADO, columna)
                print(f"Excel: fila {usuario.fila}, columna {letra} = '{nota or excel.MARCA_REALIZADO}'")
                if nota:
                    a_mano.append((usuario, numero, nota))
            else:
                terminados.append(usuario)
                # Ultimo paso: un solo PDF con todo (1, DOCUMENTO, 2, 3, 4) con el nombre de la carpeta
                print("\nUniendo los PDF del usuario:")
                try:
                    pdf.unir_pdfs(pdf.carpeta_persona(usuario))
                except Exception as e:  # el PDF unido se puede rehacer con herramientas/unir_pdfs.py
                    print(f"   [ERROR] No se pudo unir los PDF: {type(e).__name__}: {e}")
                # Y por ultimo su fila en la hoja de Google, antes de pasar a la siguiente persona
                if not usuario.hoja and not llenar_hoja(hoja, usuario):
                    hoja_pendiente.append(usuario)

        print("\n" + "=" * 70)
        print(f"Con todos los formularios enviados: {len(terminados)} | Con opcion 'Otro': {len(con_otro)} "
              f"| Enviados con algo a mano: {len(a_mano)} | No encontrados o dudosos: {len(no_encontrados)} "
              f"| Sin formulario 4 en Kobo: {len(sin_formulario)} | Pendientes: {len(pendientes)} "
              f"| Hoja de Google pendiente: {len(hoja_pendiente)}")
        for u in con_otro:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} ({excel.MARCA_OTRO})")
        for u, numero, nota in a_mano:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (formulario {numero}: {nota})")
        for u, numero, motivo in no_encontrados:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (formulario {numero}: {motivo})")
        for u, numero in sin_formulario:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (sin formulario {numero} en Kobo)")
        for u, numero in pendientes:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (falta formulario {numero})")
        for u in hoja_pendiente:
            print(f"   - fila {u.fila}: {u.usuario} {u.nombre} (falta llenar la hoja de Google)")
        excel.guardar_pendientes(esperar=True)  # lo que no se pudo guardar con el Excel abierto
        actualizar_casos()
        input("\nSe procesaron todos los pendientes. Presiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
