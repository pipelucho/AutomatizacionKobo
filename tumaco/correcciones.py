"""Correcciones que se aplican dentro del formulario de edicion (Enketo) de cada formulario."""
import base64
import json
import math
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
from playwright.sync_api import Locator, Page, TimeoutError

from . import cedula, config, firmas, reglas, ventanas
from .humano import clic, escribir, pausa, pegar
from .texto import norm, similitud_nombre

FORM = "body > div.main > article > form"

# Campos que deben quedar en MAYUSCULA, por formulario (1 = REGISTRO DE VISITA PUERTA A PUERTA)
MAYUSCULAS = {
    1: [
        f"{FORM} > section:nth-child(4) > label:nth-child(8)",
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",  # barrio
    ],
    2: [
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",  # barrio
    ],
    3: [
        f"{FORM} > section:nth-child(4) > label:nth-child(7)",  # DATOS DEL USUARIO: barrio
    ],
    4: [
        f"{FORM} > section:nth-child(4) > label:nth-child(6)",  # DATOS DEL USUARIO Y DEL INMUEBLE: barrio
    ],
}

# Direccion de la persona: en mayuscula si el numero de casa coincide con la casa del Excel (columna C);
# si esta vacia, sin numero ('No tiene numero la casa') u otro numero, se cambia por 'CASA <casa del Excel>'
DIRECCIONES = {
    1: f"{FORM} > section:nth-child(5) > label:nth-child(5)",
    2: f"{FORM} > section:nth-child(5) > label:nth-child(5)",
    3: f"{FORM} > section:nth-child(4) > label:nth-child(6)",
    4: f"{FORM} > section:nth-child(4) > label:nth-child(5)",
}

# Campos que siempre llevan el mismo valor, por formulario
VALORES_FIJOS = {
    1: [
        # RESPONSABLE CONTRATISTA: nombre y documento
        (f"{FORM} > section:nth-child(10) > section:nth-child(4) > label:nth-child(2)", "ADRIANA MUÑOZ"),
        (f"{FORM} > section:nth-child(10) > section:nth-child(4) > label:nth-child(3)", "59122110"),
    ],
    2: [
        (f"{FORM} > section:nth-child(3) > label:nth-child(9)", "ADRIANA MUÑOZ"),
        # RESPONSABLE CONTRATISTA: nombre y documento
        (f"{FORM} > section:nth-child(5) > section:nth-child(18) > label:nth-child(2)", "ADRIANA MUÑOZ"),
        (f"{FORM} > section:nth-child(5) > section:nth-child(18) > label:nth-child(3)", "59122110"),
    ],
    3: [
        # INFORMACION GENERAL: nombre (unica pregunta de texto de la seccion)
        (f"{FORM} > section:nth-child(3) > label", "ADRIANA MUÑOZ"),
        # RESPONSABLE CONTRATISTA: nombre y documento
        (f"{FORM} > section:nth-child(6) > section:nth-child(5) > label:nth-child(2)", "ADRIANA MUÑOZ"),
        (f"{FORM} > section:nth-child(6) > section:nth-child(5) > label:nth-child(3)", "59122110"),
    ],
    4: [
        # INFORMACION GENERAL: nombre (unica pregunta de texto de la seccion)
        (f"{FORM} > section:nth-child(3) > label", "ADRIANA MUÑOZ"),
        # RESPONSABLE CONTRATISTA (ingeniero residente): nombre y documento
        (f"{FORM} > section:nth-child(8) > section:nth-child(4) > label:nth-child(2)", "JHON SEBASTIAN MONTEALEGRE STERLING"),
        (f"{FORM} > section:nth-child(8) > section:nth-child(4) > label:nth-child(3)", "1032490603"),
    ],
}

# Campos que se llenan con un texto solo si estan vacios (si ya tienen algo, se respeta), por formulario
VALORES_SI_VACIO = {
    3: [
        # SERVICIOS PUBLICOS DOMICILIARIOS / OBSERVACION (OPCIONAL)
        (f"{FORM} > section:nth-child(5) > label:nth-child(96)",
         "EL AGUA ES DEFICIENTE, LA SUSPENDEN POR MÁS DE OCHO DÍAS CEDENAR NO VIENE A TOMAR LECTURA "
         "Y LAS FACTURAS NOS LLEGAN MUY CARAS TAMBIEN APAGONES"),
    ],
}

# Campos que se reemplazan con el dato del Excel de usuarios (viene corregido), por formulario.
# El segundo valor es el atributo de excel.Usuario que se escribe.
VALORES_DEL_EXCEL = {
    1: [
        # PERSONA ATENDIDA: nombre
        (f"{FORM} > section:nth-child(5) > label:nth-child(2)", "nombre"),
        # PERSONA ATENDIDA (junto a su firma): nombre
        (f"{FORM} > section:nth-child(10) > section.or-group.or-branch.or-appearance-field-list > label:nth-child(2)", "nombre"),
    ],
    2: [
        (f"{FORM} > section:nth-child(5) > label:nth-child(2)", "nombre"),
        (f"{FORM} > section:nth-child(5) > section:nth-child(17) > label:nth-child(2)", "nombre"),
    ],
    3: [
        # DATOS DEL USUARIO: nombre
        (f"{FORM} > section:nth-child(4) > label:nth-child(3)", "nombre"),
        # ENTREVISTADO (junto a su firma): nombre
        (f"{FORM} > section:nth-child(6) > section:nth-child(4) > label:nth-child(2)", "nombre"),
    ],
    4: [
        # DATOS DEL USUARIO Y DEL INMUEBLE: nombre
        (f"{FORM} > section:nth-child(4) > label:nth-child(2)", "nombre"),
        # USUARIO (junto a su firma): nombre
        (f"{FORM} > section:nth-child(8) > section:nth-child(3) > label:nth-child(2)", "nombre"),
    ],
}

# VERIFICACION DEL USUARIO, "la persona que atiende la visita manifiesta ser": si esta marcada
# la opcion "Otro", el usuario no se corrige ni se envia (se anota en el Excel)
OPCION_OTRO = {
    1: f"{FORM} > section:nth-child(6) > fieldset:nth-child(2) > fieldset > div > label:nth-child(9)",
}

# VERIFICACION DEL USUARIO, "la persona que atiende la visita manifiesta ser": la opcion marcada
# se anota en la columna H del Excel (Si = propietario(a), No = cualquier otra)
PREGUNTA_PROPIETARIO = {
    1: f"{FORM} > section:nth-child(6) > fieldset:nth-child(2)",
}

# PERSONA ATENDIDA: documento, que se guarda en la columna I del Excel para la hoja de Google
CAMPO_DOCUMENTO = {
    1: f"{FORM} > section:nth-child(5) > label:nth-child(3)",
}

# NO. USUARIO de cada formulario: si en Kobo esta vacio se llena con el del Excel (es el mismo de la hoja).
# Si ya tiene otro numero no se cambia: queda el aviso para verificar.
CAMPO_USUARIO = {
    1: f"{FORM} > section:nth-child(5) > label:nth-child(4)",
    2: f"{FORM} > section:nth-child(5) > label:nth-child(4)",
    3: f"{FORM} > section:nth-child(4) > label:nth-child(5)",
    4: f"{FORM} > section:nth-child(4) > label:nth-child(4)",
}

# Seccion donde se cargan los documentos anexos, por formulario
DOCUMENTOS = {
    1: f"{FORM} > section:nth-child(11)",
}

# Firma que se borra y se vuelve a dibujar: seccion del formulario y trazos guardados en firmas/
# "xpath": el campo de la firma en la API de Kobo, para ver si ya tiene la firma del bot y no volver a firmar
FIRMAS = {
    1: {"seccion": f"{FORM} > section:nth-child(10) > section:nth-child(4)", "trazos": "contratista.json",
        "xpath": "group_ma5xk12/grp_firma_contratista/contratista_firma"},
    2: {"seccion": f"{FORM} > section:nth-child(5) > section:nth-child(18)", "trazos": "contratista.json",  # misma firma
        "xpath": "grp_declaracion/grp_firma_contratista/contratista_firma"},
    3: {"seccion": f"{FORM} > section:nth-child(6) > section:nth-child(5)", "trazos": "contratista.json",  # misma firma
        "xpath": "declaracion_aceptacion/responsable_contratista/contratista_firma"},
    4: {"seccion": f"{FORM} > section:nth-child(8) > section:nth-child(4)", "trazos": "jhon.json",  # otra persona
        "xpath": "grp_declaracion/grp_firma_contratista/Firma"},
}

# Fotos de la cedula que se recortan al borde del documento y se enderezan: (pregunta, lado)
CEDULAS = {
    2: [
        (f"{FORM} > section:nth-child(6) > label:nth-child(2)", "cara"),
        (f"{FORM} > section:nth-child(6) > label:nth-child(3)", "reverso"),
    ],
}

SOPORTE_CON_ANEXO, SOPORTE_SIN_ANEXO = reglas.SOPORTE_CON_ANEXO, reglas.SOPORTE_SIN_ANEXO

CONFIRMAR_ELIMINAR = (
    "body > div.vex.vex-theme-plain > div > form > div.vex-dialog-buttons"
    " > button.btn.btn-primary.small.vex-dialog-button.vex-first"
)


@dataclass
class Resultado:
    cambios: list = field(default_factory=list)  # resumen de cada cambio hecho
    cedulas: dict = field(default_factory=dict)  # lado ('cara'/'reverso') -> jpg ajustado
    revisar: list = field(default_factory=list)  # lo que no se pudo hacer y queda para hacer a mano
    anexo: str | None = None  # documento anexo: "Si" si se conservo, "No" si se elimino o no habia
    soporte: str = ""  # texto para la columna J de la hoja, escrito en la ventana del documento
    avisos: list = field(default_factory=list)  # (tipo, texto): decisiones de nombre/casa para verificar
    nombre_final: str = ""  # nombre que quedo cuando Kobo es otra persona que la del Excel
    casa_final: str = ""  # casa que quedo en la direccion (ej. 'CASA 127')


def aplicar(page: Page, numero_formulario: int, usuario=None, firma_actual: bytes | None = None) -> Resultado:
    """Aplica las correcciones del formulario: que cambio, cedulas ajustadas y que revisar a mano.

    `usuario` (excel.Usuario) aporta los datos corregidos que se escriben tal cual en Kobo.
    `firma_actual`: imagen de la firma del contratista que tiene hoy el registro (de la API); si ya es la
    del bot y esta completa, no se vuelve a firmar.
    """
    resultado = Resultado()
    cambios = resultado.cambios
    _NO_QUEDARON.clear()
    if usuario is not None and numero_formulario in DIRECCIONES:
        print("\nDireccion (Excel, hoja y Kobo):")
        cambio, aviso, valor = corregir_direccion(page, DIRECCIONES[numero_formulario], getattr(usuario, "casa", ""),
                                                  getattr(usuario, "ref_direccion", ""))
        if cambio:
            cambios.append(cambio)
        if aviso:
            print(f"   [?] Verificar casa: {aviso}")
            resultado.avisos.append(("Verificar casa", aviso))
        resultado.casa_final = reglas.casa_corta(valor)
    if usuario is not None:
        print("\nDatos del Excel:")
        for selector, atributo in VALORES_DEL_EXCEL.get(numero_formulario, []):
            if atributo == "nombre":
                # El nombre se decide con Kobo, el Excel y la hoja: si es otra persona se deja el de Kobo
                # Con el nombre decidido en el formulario 1 (si fue otra persona) los 4 quedan iguales
                referencia = getattr(usuario, "nombre_final", "") or usuario.nombre
                cambio, aviso, valor = corregir_nombre(page, selector, referencia, getattr(usuario, "ref_nombre", ""))
                if aviso:
                    print(f"   [?] Verificar nombre: {aviso}")
                    resultado.avisos.append(("Verificar nombre", aviso))
                # El primer nombre del formulario es el de la persona: si quedo otro distinto al de referencia
                # (decidido por la regla o en la ventana), es el nombre final
                if (valor and not resultado.nombre_final and selector == VALORES_DEL_EXCEL[numero_formulario][0][0]
                        and similitud_nombre(valor, referencia) < reglas.UMBRAL_MISMO_NOMBRE):
                    resultado.nombre_final = valor
            else:
                valor = " ".join(str(getattr(usuario, atributo, "") or "").split()).upper()
                if not valor:
                    print(f"   [!] El Excel no tiene {atributo} para este usuario; se deja el de Kobo")
                    continue
                cambio = poner_valor(page, selector, valor)
            if cambio:
                cambios.append(cambio)
        if numero_formulario in CAMPO_USUARIO and usuario.usuario:
            cambio = llenar_usuario(page, CAMPO_USUARIO[numero_formulario], str(usuario.usuario))
            if cambio:
                cambios.append(cambio)
    if numero_formulario in MAYUSCULAS:
        print("\nMayusculas:")
    for selector in MAYUSCULAS.get(numero_formulario, []):
        cambio = poner_mayusculas(page, selector)
        if cambio:
            cambios.append(cambio)
    if numero_formulario in VALORES_FIJOS:
        print("\nValores fijos:")
        for selector, valor in VALORES_FIJOS[numero_formulario]:
            cambio = poner_valor(page, selector, valor)
            if cambio:
                cambios.append(cambio)
    if numero_formulario in VALORES_SI_VACIO:
        print("\nCampos que se llenan si estan vacios:")
        for selector, valor in VALORES_SI_VACIO[numero_formulario]:
            cambio = llenar_si_vacio(page, selector, valor)
            if cambio:
                cambios.append(cambio)
    if numero_formulario in FIRMAS:
        firma = FIRMAS[numero_formulario]
        print("\nFirma del responsable contratista:")
        ya_firmado, como = firmas.es_la_del_bot(firma_actual, firma["trazos"])
        if ya_firmado:
            print(f"   - Ya tiene la firma del bot completa ({como}): no se vuelve a firmar")
        else:
            if firma_actual:
                print(f"   - La firma actual no es la del bot o esta incompleta ({como}): se rehace")
            if rehacer_firma(page, firma["seccion"], firma["trazos"]):
                cambios.append("Firma responsable contratista: redibujada")
    if numero_formulario in CEDULAS:
        print("\nFotos de la cedula:")
        for selector, lado in CEDULAS[numero_formulario]:
            cambio, jpg, problema = ajustar_cedula(page, selector, lado, usuario)
            if cambio:
                cambios.append(cambio)
            if jpg:
                resultado.cedulas[lado] = jpg
            if problema:
                print(f"   [!] {problema[0].upper() + problema[1:]}: se deja la original para hacerlo a mano")
                resultado.revisar.append(problema)
    if numero_formulario in DOCUMENTOS:
        print("\nDocumentos anexos:")
        documentos = revisar_documentos(page, DOCUMENTOS[numero_formulario])
        for doc in documentos:
            cambios.append(f"{doc['pregunta']}: {doc['archivo']} -> {doc['decision']}")
            if doc.get("problema"):
                resultado.revisar.append(doc["problema"])
        resultado.anexo = "Si" if any(d["decision"] == "conservar" for d in documentos) else "No"
        resultado.soporte = next((d["soporte"] for d in reversed(documentos) if d.get("soporte")), "")
    # Campos que se escribieron pero al releerlos no quedaron bien: se envia igual y queda para revisar
    resultado.revisar.extend(_NO_QUEDARON)
    return resultado


def tiene_correcciones(numero_formulario: int) -> bool:
    """True si el formulario ya tiene correcciones configuradas (solo entonces se envia a Kobo)."""
    return any(numero_formulario in m for m in (MAYUSCULAS, VALORES_FIJOS, VALORES_DEL_EXCEL, VALORES_SI_VACIO,
                                                 DOCUMENTOS, FIRMAS, CEDULAS))


def inventario_campos(page: Page, numero_formulario: int) -> Path:
    """Guarda la lista de preguntas del formulario abierto (selector, texto, tipo, valor actual).

    Sirve para elegir que campos corregir en un formulario nuevo: queda en
    salida/debug/formularioN_campos.txt (legible) y .json.
    """
    campos = page.evaluate(_JS_INVENTARIO, FORM)
    config.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    base = config.DEBUG_DIR / f"formulario{numero_formulario}_campos"
    base.with_suffix(".json").write_text(json.dumps(campos, ensure_ascii=False, indent=1), encoding="utf-8")
    lineas = [f"Formulario {numero_formulario}: {len(campos)} pregunta(s)\n"]
    for c in campos:
        estado = "" if c["visible"] else "  [oculta en este registro]"
        lineas.append(f"[{c['tipo']}] {c['pregunta']}{estado}\n    valor: {c['valor'] or '(vacio)'}\n"
                      f"    selector: {c['selector']}\n")
    base.with_suffix(".txt").write_text("\n".join(lineas), encoding="utf-8")
    print(f"   Inventario de {len(campos)} campos guardado en {base.with_suffix('.txt')}")
    return base.with_suffix(".txt")


# ---------- Verificaciones previas ----------

# Notas del F1 que dicen que la casa no existe ('Lote vacio', 'Vivienda inexistente', 'inasistente', ...)
_INEXISTENTE = re.compile(r"lote\s+vac|inexistent|inasistent|vivienda\s+destruid|casa\s+se\s+cay", re.I)
_CAMPOS_NOTA = ("condiciones_especiales_otro_cual", "calidad_persona_otro_cual", "observaciones_gestion")


def vivienda_inexistente(envio: dict) -> list[str]:
    """Lo que dice el F1 (registro de la API) de que la vivienda no existe; lista vacia si no dice nada."""
    evidencia = []
    for clave, valor in (envio or {}).items():
        if not isinstance(valor, str):
            continue
        campo = clave.split("/")[-1]
        if campo == "condiciones_especiales_inmueble" and "vivienda_inexistente" in valor.split():
            evidencia.append("Condiciones especiales del inmueble: vivienda inexistente")
        elif campo in _CAMPOS_NOTA and _INEXISTENTE.search(valor):
            evidencia.append(f"{campo.replace('_', ' ').capitalize()}: {' '.join(valor.split())}")
    return evidencia


def confirmar_retirado(page: Page, usuario, evidencia: list[str]) -> bool:
    """Ventana: el F1 dice que la vivienda no existe. True = no se procesa y queda RETIRADO en la hoja."""
    if not config.PREGUNTAR_DUDAS:
        return False
    print("   ? El formulario 1 dice que la vivienda no existe -> decide en la ventana del navegador...")
    elegidos = ventanas.revisar_cambios(
        page, "La vivienda no existe (lote vacío)",
        [f"Usuario {usuario.usuario} | casa {usuario.casa} | {usuario.nombre}", *evidencia,
         "Marcar RETIRADO: no se corrige ni se envía nada; en la hoja queda I = RETIRADO, J = FOTOGRAFIA VIVIENDA.",
         "Procesar normal: se sigue como cualquier otro usuario."],
        [{"id": "retirado", "campo": "Estado en la hoja", "actual": "PENDIENTE", "nuevo": "RETIRADO", "editable": False,
          "detalle": "Desmarca o elige 'Procesar normal' para no retirarlo"}],
        aplicar="Marcar RETIRADO", omitir="Procesar normal")
    return bool(elegidos)


def notas_formulario1(envio: dict) -> list[str]:
    """Las notas del F1 (Otro cual, condiciones especiales, observaciones), sin vacias ni 'Ninguna'."""
    notas = []
    for clave, valor in (envio or {}).items():
        if clave.split("/")[-1] in _CAMPOS_NOTA and isinstance(valor, str):
            texto = " ".join(valor.split())
            if texto and norm(texto) not in ("ninguna", "ninguno", "na", "n/a", "no"):
                notas.append(texto)
    return notas


def proponer_observacion(notas: list[str]) -> str:
    """Texto para la columna L de la hoja segun las notas del F1 (como lo escriben los demas equipos)."""
    t = norm(" ".join(notas))
    if re.search(r"fallec|difunt|murio", t):
        return "BENEFICIARIO INICIAL FALLECIDO"
    if re.search(r"vend|compraventa|compr[oa]|nuev[oa]\s+(propietari|duen)", t):
        return "NUEVO PROPIETARIO"
    if re.search(r"sin soporte|no se cuenta con soporte|zona informal", t):
        return "NO SE CUENTA CON SOPORTES DE ESCRITURA PUBLICA NI COMPRAVENTA POR SER ZONA INFORMAL"
    return ""


def observacion_hoja(page: Page, usuario, envio: dict, nombre_final: str) -> str:
    """Observacion (columna L de la hoja) cuando hay algo que explicar: quien atendio es otra persona, no es
    propietario o el F1 trae una nota de venta, fallecimiento o soportes. Se decide en la ventana."""
    notas = notas_formulario1(envio)
    propuesta = proponer_observacion(notas)
    otra_persona = bool(nombre_final) or getattr(usuario, "propietario", "").lower() == "no"
    if not (propuesta or otra_persona):
        return "N/A"  # CONFIRMADO sin nada que explicar: como lo escriben los demas equipos
    if not config.PREGUNTAR_DUDAS:
        return propuesta
    print("   ? Observacion para la hoja (columna L) -> decide en la ventana del navegador...")
    elegidos = ventanas.revisar_cambios(
        page, "Observación para la hoja de Google (columna L)",
        [f"Usuario {usuario.usuario} | Excel: {usuario.nombre} | quien atendió: {nombre_final or usuario.nombre}",
         *([f"Nota en Kobo: {n}" for n in notas] or ["Kobo no trae notas"]),
         "Puedes editar el texto. 'Sin observación' deja la columna L como está."],
        [{"id": "obs", "campo": "Observación (L)", "actual": "", "nuevo": propuesta or "NUEVO PROPIETARIO",
          "detalle": "Textos que ya usan: NUEVO PROPIETARIO, BENEFICIARIO INICIAL FALLECIDO, NO SE CUENTA CON SOPORTES..."}],
        aplicar="Usar esta observación", omitir="Sin observación")
    valor = reglas.limpio((elegidos or {}).get("obs", ""))
    print(f"   - Observacion: decidido en la ventana -> '{valor or 'sin observacion'}'")
    return valor


def procesar_aunque_otro(page: Page, numero_formulario: int, usuario) -> bool:
    """Quien atiende marco 'Otro': se pregunta en la ventana si se procesa igual (como cuando atiende otra
    persona: queda el nombre de quien atendio). Con PREGUNTAR_DUDAS=0 se mantiene la regla: no se procesa."""
    if not config.PREGUNTAR_DUDAS:
        return False
    campo = page.locator(VALORES_DEL_EXCEL[numero_formulario][0][0]).locator("input, textarea").first
    quien = " ".join(campo.input_value().split()) if campo.count() else ""
    print("   ? Quien atiende marco 'Otro' -> decide en la ventana del navegador...")
    elegidos = ventanas.revisar_cambios(
        page, "Quien atiende la visita marcó 'Otro'",
        [f"Usuario {usuario.usuario} | casa {usuario.casa}",
         f"Excel: {usuario.nombre} | hoja: {getattr(usuario, 'ref_nombre', '') or '-'}",
         f"Quien atendió (Kobo): {quien or '-'}",
         "Procesar: se corrige y se envía; queda el nombre de quien atendió. Saltar: queda 'Tiene otro'."],
        [{"id": "otro", "campo": "Quien atiende", "actual": "Otro", "nuevo": "Procesar igual", "editable": False,
          "detalle": "Desmarca o elige 'Saltar' para no procesarlo"}],
        aplicar="Procesar", omitir="Saltar (Tiene otro)")
    return bool(elegidos)


def marco_opcion_otro(page: Page, numero_formulario: int) -> bool | None:
    """True si en 'la persona que atiende la visita manifiesta ser' esta marcada la opcion 'Otro'.

    None si no se pudo verificar (la opcion no esta o el selector apunta a otra respuesta):
    en ese caso el usuario queda pendiente para revisarlo a mano.
    """
    selector = OPCION_OTRO.get(numero_formulario)
    if not selector:
        return False
    opcion = page.locator(selector).first
    if not opcion.count():
        print(f"   [!] No encontre la opcion 'Otro': {selector}")
        return None
    texto = " ".join(opcion.inner_text().split())
    if not norm(texto).startswith("otro"):
        print(f"   [!] La opcion encontrada no es 'Otro' (dice: '{texto}'); revisa el selector")
        return None
    entrada = opcion.locator("input[type=radio], input[type=checkbox]").first
    if not entrada.count():
        print(f"   [!] La opcion '{texto}' no tiene casilla para verificar")
        return None
    marcado = entrada.is_checked()
    print(f"   - Opcion '{texto}': {'MARCADA' if marcado else 'no marcada'}")
    return marcado


def es_propietario(page: Page, numero_formulario: int) -> tuple[str, str] | None:
    """('Si' | 'No' | 'Sin respuesta', opcion marcada) segun 'la persona que atiende la visita manifiesta ser'.

    None si el formulario no tiene esa pregunta configurada o no se encontro.
    """
    selector = PREGUNTA_PROPIETARIO.get(numero_formulario)
    if not selector:
        return None
    pregunta = page.locator(selector).first
    if not pregunta.count():
        print(f"   [!] No encontre la pregunta de propietario: {selector}")
        return None
    opcion = pregunta.evaluate(
        "f => { const i = f.querySelector('input[type=radio]:checked');"
        " return i ? (i.closest('label') || i.parentElement).innerText.trim() : ''; }")
    if not opcion:
        return "Sin respuesta", ""
    return ("Si" if norm(opcion).startswith("propietari") else "No"), opcion


def hay_documento_anexo(page: Page, numero_formulario: int) -> str | None:
    """'Si' si el formulario tiene hoy un documento anexo cargado, 'No' si no (sin preguntar nada).
    Sirve para completar la columna J de formularios hechos antes de guardar ese dato."""
    selector = DOCUMENTOS.get(numero_formulario)
    seccion = page.locator(selector) if selector else None
    if seccion is None or not seccion.count():
        return None
    preguntas = seccion.locator("label:has(input[type=file])")
    cargados = [preguntas.nth(i).evaluate(_JS_INFO_DOCUMENTO)["archivo"] for i in range(preguntas.count())]
    return "Si" if any(cargados) else "No"


def leer_documento(page: Page, numero_formulario: int) -> str | None:
    """Documento de la persona atendida, solo los numeros (ej. '596318 47' -> '59631847').

    None si el formulario no tiene ese campo configurado o no se encontro.
    """
    selector = CAMPO_DOCUMENTO.get(numero_formulario)
    if not selector:
        return None
    campo = page.locator(selector).locator("input").first
    if not campo.count():
        print(f"   [!] No encontre el campo de documento: {selector}")
        return None
    return "".join(c for c in campo.input_value() if c.isdigit())


# ---------- Campos de texto ----------

def poner_mayusculas(page: Page, selector: str) -> str | None:
    return _corregir_texto(page, selector, lambda actual: actual.strip().upper(), "ya esta en mayuscula")


def poner_valor(page: Page, selector: str, valor: str) -> str | None:
    return _corregir_texto(page, selector, lambda _: valor, "ya tiene el valor correcto")


def llenar_si_vacio(page: Page, selector: str, valor: str) -> str | None:
    # Son textos largos: se pegan de una vez en lugar de escribirlos letra por letra
    return _corregir_texto(page, selector, lambda actual: actual if actual.strip() else valor,
                           "ya tiene texto, se deja igual", pegando=True)


def llenar_usuario(page: Page, selector: str, numero: str) -> str | None:
    """NO. USUARIO: si esta vacio se pone el del Excel (es el mismo de la hoja). Si tiene otro numero se
    pregunta en la ventana, proponiendo el del Excel (con PREGUNTAR_DUDAS=0 se cambia y queda el aviso)."""
    def transformar(actual: str) -> str:
        if not actual.strip():
            return numero
        if "".join(c for c in actual if c.isdigit()) == numero:
            return actual
        aviso = f"Kobo dice '{actual}' y el Excel y la hoja dicen '{numero}'"
        valor, aviso = _preguntar_duda(page, "No. Usuario", actual, numero, actual, aviso,
                                       [f"Excel y hoja (No. Usuario): {numero}"])
        if aviso:
            print(f"   [?] Verificar usuario: {aviso}")
        return valor

    return _corregir_texto(page, selector, transformar, "ya tiene usuario")


def corregir_direccion(page: Page, selector: str, casa_excel: str,
                       direccion_hoja: str = "") -> tuple[str | None, str | None, str]:
    """Direccion decidida con Kobo, el Excel y la hoja (ver reglas.decidir_casa).
    Devuelve (cambio hecho, aviso para verificar, direccion que quedo)."""
    decision = {}

    def transformar(actual: str) -> str:
        valor, aviso = reglas.decidir_casa(actual, casa_excel, direccion_hoja)
        if aviso:  # duda real: se pregunta en el momento en vez de corregir despues
            valor, aviso = _preguntar_duda(page, "Dirección", actual, valor, reglas.normalizar_direccion(actual), aviso,
                                           [f"Excel (casa): {casa_excel or '-'}", f"Hoja (direccion inicial): {direccion_hoja or '-'}"])
        decision["valor"], decision["aviso"] = valor, aviso
        return valor

    cambio = _corregir_texto(page, selector, transformar, "ya esta bien")
    return cambio, decision.get("aviso"), decision.get("valor", "")


def corregir_nombre(page: Page, selector: str, nombre_excel: str,
                    nombre_hoja: str = "") -> tuple[str | None, str | None, str]:
    """Nombre decidido con Kobo, el Excel y la hoja (ver reglas.decidir_nombre).
    Devuelve (cambio hecho, aviso para verificar, nombre que quedo)."""
    decision = {}

    def transformar(actual: str) -> str:
        valor, aviso = reglas.decidir_nombre(actual, nombre_excel, nombre_hoja)
        if aviso:  # parece otra persona: se pregunta en el momento en vez de corregir despues
            valor, aviso = _preguntar_duda(page, "Nombre", actual, valor, reglas.limpio(actual), aviso,
                                           [f"Excel: {nombre_excel or '-'}", f"Hoja (usuario inicial): {nombre_hoja or '-'}"])
        decision["valor"], decision["aviso"] = valor, aviso
        return valor

    cambio = _corregir_texto(page, selector, transformar, "ya tiene el valor correcto")
    return cambio, decision.get("aviso"), decision.get("valor", "")


def _preguntar_duda(page: Page, campo: str, actual: str, propuesto: str, kobo: str, aviso: str,
                    fuentes: list[str]) -> tuple[str, str | None]:
    """Cuando Kobo, el Excel y la hoja no coinciden, muestra la ventana para decidir en el momento.

    Devuelve (valor que queda, aviso). Si decides en la ventana no queda aviso para verificar despues.
    Con PREGUNTAR_DUDAS=0 en .env no pregunta: aplica la regla y deja el aviso en CASOS.xlsx.
    """
    if not config.PREGUNTAR_DUDAS:
        return propuesto, aviso
    print(f"   ? {campo}: {aviso} -> decide en la ventana del navegador...")
    elegidos = ventanas.revisar_cambios(
        page, f"{campo}: Kobo, el Excel y la hoja no coinciden", [f"Kobo hoy: {actual or '(vacío)'}", *fuentes, aviso],
        [{"id": "v", "campo": campo, "actual": actual, "nuevo": propuesto,
          "detalle": "Propuesta del bot; puedes editarla. 'Dejar lo de Kobo' no cambia este dato."}],
        aplicar="Usar este valor", omitir="Dejar lo de Kobo")
    valor = elegidos["v"] if elegidos else kobo
    print(f"   - {campo}: decidido en la ventana -> '{valor}'")
    return reglas.limpio(valor), None


# Campos escritos que al releerlos no quedaron con el valor esperado (se pasan a resultado.revisar)
_NO_QUEDARON: list[str] = []


def _corregir_texto(page: Page, selector: str, transformar, msg_sin_cambio: str,
                    pegando: bool = False) -> str | None:
    """Reescribe el campo con transformar(valor_actual) si el resultado es distinto, y lo relee
    para verificar que quedo bien (si no, reintenta una vez y si sigue mal lo anota para revisar).

    pegando=True pone el texto de una vez (como Ctrl+V) en lugar de escribirlo tecla por tecla.
    """
    pregunta = page.locator(selector)
    if not pregunta.count():
        print(f"   [!] No encontre el campo: {selector}")
        return None
    nombre = (pregunta.locator(".question-label").first.inner_text() if pregunta.locator(".question-label").count()
              else selector).strip()
    campo = pregunta.locator("input:not([type=hidden]):not([type=radio]):not([type=checkbox]), textarea").first
    if not campo.count() or not campo.is_visible():
        print(f"   - {nombre}: no aplica en este registro (campo oculto)")
        return None

    actual = campo.input_value()
    nuevo = transformar(actual)
    if actual == nuevo:
        print(f"   - {nombre}: {msg_sin_cambio} ({actual or 'vacio'})")
        return None

    campo.scroll_into_view_if_needed()
    pausa(page, 0.3, 0.8)
    (pegar if pegando else escribir)(campo, nuevo)
    campo.dispatch_event("change")  # Enketo guarda el valor al detectar el cambio
    if campo.input_value() != nuevo:  # verificar: a veces se pierde una letra o se corta
        campo.fill(nuevo)
        campo.dispatch_event("change")
        if (quedo := campo.input_value()) != nuevo:
            print(f"   [!] {nombre}: quedo '{quedo}' y debia ser '{nuevo}'")
            _NO_QUEDARON.append(f"{nombre.lower()} no quedo bien ('{quedo}')")
            return f"{nombre}: {actual} -> {quedo} (no quedo como se esperaba)"
    print(f"   * {nombre}: '{actual}' -> '{nuevo}'")
    return f"{nombre}: {actual} -> {nuevo}"


# ---------- Firma ----------

def _dibujar(page: Page, trazos: list[list[tuple[float, float]]], paso_px: float = 12):
    """Dibuja los trazos como una mano: boton presionado y un movimiento cada ~17 ms.

    Va directo al navegador (eventos reales de mouse por CDP) para no pagar la pausa fija de
    SLOW_MO en cada punto: asi el trazo sale continuo y el lienzo le da el grosor de un trazo a
    mano. Entre puntos se agregan intermedios cada `paso_px` (solo en tramos rectos: los puntos que
    dan la forma se conservan). El ritmo descuenta lo que tarda cada envio, para no sumar esperas.
    """
    cdp = page.context.new_cdp_session(page)

    def mouse(tipo, x, y, presionado):
        cdp.send("Input.dispatchMouseEvent", {
            "type": tipo, "x": x, "y": y, "button": "left", "buttons": 1 if presionado else 0, "clickCount": 1,
        })

    try:
        for trazo in trazos:
            puntos = [trazo[0]]
            for (xa, ya), (xb, yb) in zip(trazo, trazo[1:]):
                n = max(1, math.ceil(math.hypot(xb - xa, yb - ya) / paso_px))
                puntos += [(xa + (xb - xa) * k / n, ya + (yb - ya) * k / n) for k in range(1, n + 1)]
            mouse("mouseMoved", *puntos[0], False)
            mouse("mousePressed", *puntos[0], True)
            siguiente = time.perf_counter()
            for x, y in puntos[1:]:
                siguiente += random.uniform(0.0165, 0.019)  # el lienzo ignora movimientos de menos de 16 ms
                if (espera := siguiente - time.perf_counter()) > 0:
                    time.sleep(espera)
                mouse("mouseMoved", x, y, True)
            mouse("mouseReleased", *puntos[-1], False)
            time.sleep(random.uniform(0.04, 0.09))
    finally:
        cdp.detach()


def rehacer_firma(page: Page, selector_seccion: str, archivo_trazos: str) -> bool:
    """Borra la firma del lienzo (boton del pie + Aceptar) y la dibuja de nuevo con el mouse."""
    ruta = config.FIRMAS_DIR / archivo_trazos
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}; crea los trazos con herramientas/firma_desde_imagen.py "
                                "(el formulario no se envia sin su firma)")
    firma = json.loads(ruta.read_text(encoding="utf-8"))

    pregunta = page.locator(f"{selector_seccion} > label.or-appearance-signature").first
    if not pregunta.count():
        print(f"   [!] No encontre el campo de firma en {selector_seccion}")
        return False
    lienzo = pregunta.locator("canvas").first
    lienzo.evaluate("el => el.scrollIntoView({block: 'center'})")
    pausa(page, 0.2, 0.4)

    # 1. Borrar la firma actual
    clic(pregunta.locator("div.draw-widget__footer > button").first)
    confirmar = page.locator(CONFIRMAR_ELIMINAR)
    try:
        confirmar.wait_for(timeout=5_000)
        clic(confirmar)
        confirmar.wait_for(state="detached", timeout=10_000)
        print("   - Firma anterior borrada")
    except TimeoutError:
        print("   - No habia firma para borrar")

    # 2. Dibujarla centrada en el lienzo, ocupando hasta el 80% del espacio
    lienzo.evaluate("el => el.scrollIntoView({block: 'center'})")
    pausa(page, 0.1, 0.2)
    caja = lienzo.bounding_box()
    escala = min(0.8 * caja["width"] / firma["ancho"], 0.8 * caja["height"] / firma["alto"])
    x0 = caja["x"] + (caja["width"] - firma["ancho"] * escala) / 2
    y0 = caja["y"] + (caja["height"] - firma["alto"] * escala) / 2

    def punto(p):
        return x0 + p[0] * firma["ancho"] * escala, y0 + p[1] * firma["alto"] * escala

    _dibujar(page, [[punto(p) for p in trazo] for trazo in firma["trazos"]])
    pausa(page, 0.2, 0.4)  # que el lienzo guarde la firma
    print(f"   * Firma dibujada ({len(firma['trazos'])} trazos)")
    return True


# ---------- Fotos de la cedula ----------

def ajustar_cedula(page: Page, selector: str, lado: str, usuario=None) -> tuple[str | None, bytes | None, str | None]:
    """Recorta la foto de la cedula al borde del documento, la endereza y la vuelve a subir.

    Devuelve (cambio, jpg ajustado, problema):
    - sin foto cargada: (None, None, None) -> se salta este paso.
    - ajustada y subida: (resumen, jpg, None).
    - hay foto pero no se pudo ajustar con seguridad: (None, None, motivo) -> se deja la
      original y el motivo se anota en el Excel para hacerlo a mano.
    El original y el ajuste quedan guardados en salida/cedulas/.
    """
    pregunta = page.locator(selector).first
    if not pregunta.count():
        return None, None, f"no encontre el campo de la cedula {lado}"
    info = pregunta.evaluate(_JS_INFO_DOCUMENTO)
    if not info["archivo"]:
        print(f"   - Cedula {lado}: sin foto cargada, se salta")
        return None, None, None
    if not info["imagen"]:
        return None, None, f"la cedula {lado} no es una imagen ({info['archivo']})"

    pregunta.scroll_into_view_if_needed()
    print(f"   - Cedula {lado}: descargando {info['archivo']}...")
    esperar_imagen(page, pregunta)  # las fotos de celular son pesadas: que termine de cargar
    info = pregunta.evaluate(_JS_INFO_DOCUMENTO)
    datos = _descargar_imagen(page, pregunta, info["imagen"]) if info["imagen"] else None
    if not datos:
        return None, None, f"no se pudo descargar la cedula {lado}"
    foto = cedula.leer(datos)
    if foto is None:
        return None, None, f"la cedula {lado} no es una imagen valida"
    if "-ajustada" in info["archivo"]:  # ya se ajusto en una corrida anterior: no se recorta otra vez
        print(f"   - Cedula {lado}: ya estaba ajustada ({info['archivo']})")
        return None, cedula.a_jpg(foto), None

    carpeta = config.OUTPUT_DIR / "cedulas"
    carpeta.mkdir(parents=True, exist_ok=True)
    prefijo = f"{getattr(usuario, 'usuario', '') or 'sin_usuario'}_{lado}"
    (carpeta / f"{prefijo}_original{Path(info['archivo']).suffix or '.jpg'}").write_bytes(datos)

    resultado = cedula.enderezar_cedula(foto, lado)
    if resultado is None:
        ajustada = _cedula_a_mano(page, foto, lado, None, "no encontre el borde de la cedula en la foto")
        if ajustada is None:
            return None, None, f"no se encontro el borde de la cedula {lado} en la foto"
        nota = "aceptada tal como estaba" if ajustada is foto else "ajustada a mano"
    else:
        ajustada, seguro, nota = resultado
        if not seguro:
            (carpeta / f"{prefijo}_dudosa.jpg").write_bytes(cedula.a_jpg(ajustada))
            ajustada = _cedula_a_mano(page, foto, lado, ajustada, "no estoy seguro de hacia donde va arriba")
            if ajustada is None:
                return None, None, f"no es seguro hacia donde va arriba la cedula {lado}"
            nota = "revisada a mano"

    jpg = cedula.a_jpg(ajustada)
    (carpeta / f"{prefijo}_ajustada.jpg").write_bytes(jpg)
    nombre = f"{Path(info['archivo']).stem}-ajustada.jpg"
    if not reemplazar_archivo(page, pregunta, nombre, jpg):
        return None, None, f"no se pudo subir la cedula {lado} ajustada"
    print(f"   * Cedula {lado}: recortada y enderezada ({nota})")
    return f"Cedula {lado}: {info['archivo']} -> {nombre}", jpg, None


def _cedula_a_mano(page: Page, foto, lado: str, propuesta, motivo: str):
    """Cuando el ajuste automatico no es seguro, pregunta en una ventana sobre el formulario.

    Con propuesta: se ve la cedula recortada con 'Usar asi', 'Girar 180', 'Marcar esquinas' y
    'Dejar la original'. Marcar esquinas muestra la foto original para dar clic en las 4 esquinas de
    la tarjeta; se recorta, se endereza y se vuelve a mostrar para confirmar.
    Devuelve la imagen elegida, o None si se deja la original (queda 'Revisar a mano' en el Excel).
    """
    actual = propuesta
    while True:
        if actual is not None:
            print(f"   ? Cedula {lado}: {motivo} -> revisa la ventana en el navegador...")
            r = _preguntar_cedula(page, {"modo": "revisar", "imagen": _data_url(actual),
                                         "titulo": f"Cédula ({lado}): {motivo}"})
            if r["accion"] == "usar":
                return cv2.rotate(actual, cv2.ROTATE_180) if r.get("girada") else actual
            if r["accion"] == "original":
                return None
        print(f"   ? Cedula {lado}: marca las 4 esquinas en la ventana del navegador...")
        r = _preguntar_cedula(page, {"modo": "esquinas", "imagen": _data_url(foto, 1400),
                                     "titulo": f"Cédula ({lado}): {motivo}"})
        if r["accion"] == "asi":  # 'Listo' sin marcar puntos: la foto ya estaba bien
            print(f"   - Cedula {lado}: se deja tal como esta (decidido en la ventana)")
            return foto
        if r["accion"] != "esquinas" or len(r.get("puntos", [])) != 4:
            return None
        escala = foto.shape[1] / r["ancho"]  # de la imagen mostrada (reducida) a la foto original
        actual, _ = cedula.orientar(cedula.recortar_por_esquinas(foto, [(x * escala, y * escala)
                                                                        for x, y in r["puntos"]]), lado)
        motivo = "revisa el recorte con las esquinas que marcaste"


def _data_url(img, lado_maximo: int = 1200) -> str:
    escala = min(1.0, lado_maximo / max(img.shape[:2]))
    if escala < 1:
        img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _preguntar_cedula(page: Page, info: dict) -> dict:
    page.evaluate(_JS_MODAL_CEDULA, info)
    page.wait_for_function("() => window.__tumacoCedula", timeout=0, polling=500)
    return json.loads(page.evaluate("() => { const r = window.__tumacoCedula; delete window.__tumacoCedula; return r; }"))


# Ventana para revisar la cedula (usar / girar / marcar esquinas / dejar original) o marcar sus 4 esquinas
_JS_MODAL_CEDULA = r"""
(info) => {
  document.getElementById('tumaco-cedula')?.remove();
  const m = document.createElement('div');
  m.id = 'tumaco-cedula';
  m.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif">
      <div style="background:#fff;border-radius:10px;width:94vw;max-width:1100px;max-height:94vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)">
        <div style="padding:14px 18px;border-bottom:1px solid #ddd">
          <div id="tc-titulo" style="font-size:17px;font-weight:bold;color:#222"></div>
          <div id="tc-ayuda" style="font-size:14px;color:#555;margin-top:4px"></div>
        </div>
        <div id="tc-vista" style="flex:1;overflow:auto;padding:10px;text-align:center;background:#f2f2f2"></div>
        <div id="tc-botones" style="padding:12px 18px;border-top:1px solid #ddd;display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end"></div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#tc-titulo').textContent = info.titulo;
  const ayuda = m.querySelector('#tc-ayuda');
  const marco = document.createElement('div');
  marco.style.cssText = 'position:relative;display:inline-block';
  const img = document.createElement('img');
  img.src = info.imagen;
  img.style.cssText = 'max-width:100%;max-height:66vh;display:block;transition:transform .2s;user-select:none';
  img.draggable = false;
  marco.appendChild(img);
  m.querySelector('#tc-vista').appendChild(marco);
  const responder = (r) => { window.__tumacoCedula = JSON.stringify(r); m.remove(); };
  const boton = (texto, principal, fn) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = texto;
    b.style.cssText = `padding:10px 18px;font-size:15px;border-radius:6px;cursor:pointer;border:1px solid ${principal ? '#1976d2' : '#bbb'};background:${principal ? '#1976d2' : '#fff'};color:${principal ? '#fff' : '#222'}`;
    b.onclick = fn;
    m.querySelector('#tc-botones').appendChild(b);
    return b;
  };

  if (info.modo === 'revisar') {
    ayuda.textContent = 'Revisa que la cédula quede recortada al borde y derecha (no de cabeza).';
    let girada = false;
    boton('Girar 180°', false, () => { girada = !girada; img.style.transform = girada ? 'rotate(180deg)' : ''; });
    boton('Marcar esquinas', false, () => responder({accion: 'esquinas'}));
    boton('Dejar la original', false, () => responder({accion: 'original'}));
    boton('Usar así', true, () => responder({accion: 'usar', girada}));
    return;
  }

  ayuda.textContent = 'Haz clic en las 4 esquinas de la cédula, en cualquier orden. '
    + 'Si la foto ya está bien recortada y derecha, da "Listo" sin marcar puntos.';
  img.style.cursor = 'crosshair';
  const puntos = [];
  // Sin puntos: se acepta la foto tal como esta. Con 4: se recorta por las esquinas. Con 1 a 3: faltan esquinas
  const listo = boton('Listo (dejarla así)', true, () => responder(puntos.length === 4
    ? {accion: 'esquinas', puntos, ancho: img.naturalWidth} : {accion: 'asi'}));
  const actualizar = () => {
    const vale = puntos.length === 0 || puntos.length === 4;
    listo.disabled = !vale;
    listo.style.opacity = vale ? 1 : .5;
    listo.textContent = puntos.length === 4 ? 'Listo (recortar)' : puntos.length === 0 ? 'Listo (dejarla así)' : `Listo (${puntos.length} de 4)`;
  };
  const reiniciar = () => {
    puntos.length = 0;
    marco.querySelectorAll('.tc-punto').forEach(d => d.remove());
    actualizar();
  };
  boton('Borrar puntos', false, reiniciar);
  boton('Dejar la original', false, () => responder({accion: 'original'}));
  img.onclick = (e) => {
    if (puntos.length >= 4) return;
    const r = img.getBoundingClientRect();
    puntos.push([(e.clientX - r.left) * img.naturalWidth / r.width, (e.clientY - r.top) * img.naturalHeight / r.height]);
    const d = document.createElement('div');
    d.className = 'tc-punto';
    d.textContent = puntos.length;
    d.style.cssText = `position:absolute;left:${e.clientX - r.left - 11}px;top:${e.clientY - r.top - 11}px;width:22px;height:22px;border-radius:50%;background:#e53935;color:#fff;font:bold 13px/22px Arial;text-align:center;pointer-events:none;box-shadow:0 0 0 2px #fff`;
    marco.appendChild(d);
    actualizar();
  };
}
"""


def _descargar_imagen(page: Page, pregunta: Locator, src: str, intentos: int = 4) -> bytes | None:
    """Bytes de la imagen que muestra el formulario (enlace de Kobo, blob: o data:).

    Prueba varias formas y reintenta con esperas crecientes (Kobo a veces tarda o falla una vez).
    """
    if src.startswith("data:"):
        return base64.b64decode(src.split(",", 1)[1])
    formas = [
        ("navegador", lambda: base64.b64decode(page.evaluate(_JS_LEER_URL, src) or "")),
        ("sesion de Kobo", lambda: _bajar_con_sesion(page, src)),
        ("imagen cargada", lambda: base64.b64decode(pregunta.evaluate(_JS_LEER_IMG) or "")),
    ]
    if not src.startswith("blob:"):  # un enlace normal: primero con la sesion (no depende de CORS)
        formas.insert(0, formas.pop(1))
    for intento in range(1, intentos + 1):
        for nombre, forma in formas:
            try:
                datos = forma()
                if datos and len(datos) > 1000:
                    return datos
            except Exception as e:
                print(f"   (descarga por {nombre} fallo: {str(e).splitlines()[0][:120]})")
        if intento < intentos:
            espera = 2 * intento
            print(f"   (no se pudo descargar la imagen, reintento {intento + 1}/{intentos} en {espera} s)")
            page.wait_for_timeout(espera * 1000)
    return None


def _bajar_con_sesion(page: Page, src: str) -> bytes | None:
    resp = page.request.get(src, timeout=90_000)  # usa la sesion de Kobo del navegador
    if not resp.ok:
        raise RuntimeError(f"Kobo respondio {resp.status}")
    return resp.body()


def esperar_imagen(page: Page, pregunta: Locator, timeout_ms: int = 30_000) -> bool:
    """Espera a que la vista previa de la imagen de la pregunta este completamente cargada."""
    try:
        page.wait_for_function(
            "(el) => { const i = el.querySelector('.file-preview img');"
            " return !!i && !!i.src && i.complete && i.naturalWidth > 0; }",
            arg=pregunta.element_handle(), timeout=timeout_ms, polling=300)
        return True
    except TimeoutError:
        print("   (la vista previa de la imagen no termino de cargar)")
        return False


def reemplazar_archivo(page: Page, pregunta: Locator, nombre: str, datos: bytes) -> bool:
    """Quita el archivo cargado (boton + Aceptar) y sube el nuevo en la misma pregunta. True si quedo."""
    if pregunta.locator(".file-preview img, .fake-file-input").count():
        boton = pregunta.locator(":scope > div > button").first
        if boton.count():
            clic(boton)
            confirmar = page.locator(CONFIRMAR_ELIMINAR)
            try:
                confirmar.wait_for(timeout=5_000)
                pausa(page, 0.3, 0.7)
                clic(confirmar)
                confirmar.wait_for(state="detached", timeout=10_000)
            except TimeoutError:
                pass  # algunos campos reemplazan sin pedir confirmacion
    entrada = pregunta.locator("input[type=file]").first
    entrada.set_input_files({"name": nombre, "mimeType": "image/jpeg", "buffer": datos})
    # Esperar a que Enketo muestre el archivo nuevo
    try:
        page.wait_for_function(
            "([el, n]) => (el.querySelector('.fake-file-input')?.value || el.querySelector('.fake-file-input')?.innerText || '').includes(n.split('.')[0])",
            arg=[pregunta.element_handle(), nombre], timeout=30_000)
    except TimeoutError:
        print(f"   [!] Enketo no mostro el archivo nuevo ({nombre})")
        return False
    esperar_imagen(page, pregunta)  # que la foto nueva ya se vea antes de seguir (PDF y envio)
    pausa(page, 0.5, 1.0)
    return True


# ---------- Documentos anexos ----------

def revisar_documentos(page: Page, selector_seccion: str) -> list[dict]:
    """Muestra cada documento cargado en una ventana sobre el formulario y pregunta si se conserva.

    Si se elige eliminar, se da clic en el boton de borrar del campo y se confirma.
    """
    seccion = page.locator(selector_seccion)
    if not seccion.count():
        print(f"   [!] No encontre la seccion de documentos: {selector_seccion}")
        return []

    resultados = []
    preguntas = seccion.locator("label:has(input[type=file])")
    for i in range(preguntas.count()):
        pregunta = preguntas.nth(i)
        info = pregunta.evaluate(_JS_INFO_DOCUMENTO)
        if not info["visible"]:
            continue  # pregunta que no aplica en este registro
        if not info["archivo"]:
            print(f"   - {info['pregunta']}: sin documento cargado, se continua")
            continue

        pregunta.scroll_into_view_if_needed()
        print(f"   ? {info['pregunta']}: {info['archivo']} -> esperando tu decision en el navegador...")
        page.evaluate(_JS_MODAL, {**info, "soportes": {"conservar": SOPORTE_CON_ANEXO, "eliminar": SOPORTE_SIN_ANEXO}})
        page.wait_for_function("() => window.__tumacoDecision", timeout=0, polling=500)
        respuesta = json.loads(page.evaluate(
            "() => { const d = window.__tumacoDecision; delete window.__tumacoDecision; return d; }"))
        decision = respuesta["decision"]
        soporte = " ".join(respuesta.get("soporte", "").split()).upper()

        problema = ""
        if decision == "eliminar":
            eliminar_documento(page, pregunta)
            print(f"   * {info['pregunta']}: ELIMINADO ({info['archivo']})")
        else:
            print(f"   - {info['pregunta']}: se conserva ({info['archivo']})")
            giro = int(respuesta.get("giro") or 0) % 360
            if giro and info["imagen"]:
                problema = girar_documento(page, pregunta, info, giro)
        if soporte:
            print(f"   - Soportes para la hoja (columna J): {soporte}")
        resultados.append({"pregunta": info["pregunta"], "archivo": info["archivo"], "decision": decision,
                           "soporte": soporte, "problema": problema})
    return resultados


def girar_documento(page: Page, pregunta: Locator, info: dict, giro: int) -> str:
    """Reemplaza el documento por su version girada `giro` grados (sentido del reloj). '' si quedo bien."""
    datos = _descargar_imagen(page, pregunta, info["imagen"])
    foto = cedula.leer(datos) if datos else None
    if foto is None:
        print("   [!] No se pudo descargar el documento para girarlo")
        return "no se pudo girar el documento anexo"
    rotacion = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[giro]
    jpg = cedula.a_jpg(cv2.rotate(foto, rotacion), ancho_maximo=2200)
    nombre = f"{Path(info['archivo']).stem}-girada.jpg"
    if not reemplazar_archivo(page, pregunta, nombre, jpg):
        return "no se pudo subir el documento anexo girado"
    print(f"   * {info['pregunta']}: girado {giro}° y vuelto a subir ({nombre})")
    return ""


def eliminar_documento(page: Page, pregunta: Locator):
    clic(pregunta.locator(":scope > div > button").first)
    confirmar = page.locator(CONFIRMAR_ELIMINAR)
    confirmar.wait_for(timeout=10_000)
    pausa(page, 0.4, 0.9)
    clic(confirmar)
    confirmar.wait_for(state="detached", timeout=10_000)


# Nombre de la pregunta, nombre del archivo cargado y direccion para verlo (imagen o descarga)
_JS_INFO_DOCUMENTO = r"""
(label) => {
  const texto = el => (el ? (el.value || el.innerText || el.textContent || '') : '').trim();
  const input = label.querySelector('input[type=file]');
  // Enketo deja el boton de descarga y la vista previa aunque no haya archivo: solo cuentan con direccion real
  const img = [...label.querySelectorAll('.file-preview img')].find(i => (i.getAttribute('src') || '').trim());
  const enlace = [...label.querySelectorAll('a.btn-download, .file-feedback a, a[download]')].find(a => {
    const h = (a.getAttribute('href') || '').trim();
    return h && h !== '#' && !h.startsWith('javascript') && a.href !== location.href;
  });
  const archivo = texto(label.querySelector('.fake-file-input'))
    || (input && input.getAttribute('data-loaded-file-name'))
    || (img || enlace ? 'documento cargado' : '');
  return {
    pregunta: texto(label.querySelector('.question-label')) || 'Documento',
    archivo,
    imagen: img ? img.src : null,
    enlace: enlace ? enlace.href : null,
    visible: label.offsetParent !== null,
  };
}
"""

# Ventana sobre el formulario con el documento y las opciones Conservar / Eliminar
_JS_MODAL = r"""
(info) => {
  document.getElementById('tumaco-modal')?.remove();
  const m = document.createElement('div');
  m.id = 'tumaco-modal';
  m.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif">
      <div style="background:#fff;border-radius:10px;max-width:900px;width:92vw;max-height:92vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)">
        <div style="padding:16px 20px;border-bottom:1px solid #ddd">
          <div style="font-size:13px;color:#666">Documento anexo</div>
          <div id="tm-pregunta" style="font-size:18px;font-weight:bold;color:#222"></div>
          <div id="tm-archivo" style="font-size:13px;color:#444;margin-top:4px"></div>
        </div>
        <div id="tm-vista" style="flex:1;overflow:auto;padding:12px;text-align:center;background:#f4f4f4;min-height:200px"></div>
        <div style="padding:16px 20px;border-top:1px solid #ddd;display:flex;align-items:center;gap:24px;flex-wrap:wrap">
          <span style="font-size:15px;font-weight:bold">¿Se conserva este documento?</span>
          <label style="font-size:16px;cursor:pointer"><input type="radio" name="tm-decision" value="conservar"> Si, conservar</label>
          <label style="font-size:16px;cursor:pointer"><input type="radio" name="tm-decision" value="eliminar"> No, eliminar</label>
          <button id="tm-ok" disabled style="margin-left:auto;padding:10px 22px;font-size:15px;border:0;border-radius:6px;background:#1976d2;color:#fff;cursor:pointer;opacity:.5">Continuar</button>
          <label style="flex-basis:100%;font-size:14px;color:#333">Soportes para la hoja de Google (columna J):
            <input id="tm-soporte" type="text" placeholder="Elige conservar o eliminar"
                   style="display:block;width:100%;margin-top:6px;padding:8px;font-size:15px;border:1px solid #bbb;border-radius:4px">
          </label>
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#tm-pregunta').textContent = info.pregunta;
  m.querySelector('#tm-archivo').textContent = info.archivo;

  const vista = m.querySelector('#tm-vista');
  let giro = 0;  // grados en sentido del reloj para dejar el documento derecho
  if (info.imagen) {
    const barra = document.createElement('div');
    barra.style.cssText = 'display:flex;gap:8px;justify-content:center;align-items:center;margin-bottom:8px;font-size:14px';
    const estado = document.createElement('span');
    const img = new Image();
    const lienzo = document.createElement('canvas');  // se dibuja girado: ocupa el espacio real y muestra como quedara
    const orientar = () => {
      estado.textContent = giro ? `Girado ${giro}°` : 'Sin girar';
      if (!img.naturalWidth) return;
      const vertical = giro % 180 !== 0;
      const escala = Math.min(1, 1400 / Math.max(img.naturalWidth, img.naturalHeight));
      const w = img.naturalWidth * escala, h = img.naturalHeight * escala;
      lienzo.width = Math.round(vertical ? h : w);
      lienzo.height = Math.round(vertical ? w : h);
      const ctx = lienzo.getContext('2d');
      ctx.translate(lienzo.width / 2, lienzo.height / 2);
      ctx.rotate(giro * Math.PI / 180);
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
    };
    for (const [texto, paso] of [['⟲ Girar a la izquierda', -90], ['⟳ Girar a la derecha', 90]]) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = texto;
      b.style.cssText = 'padding:7px 12px;font-size:14px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer';
      b.onclick = () => { giro = (giro + paso + 360) % 360; orientar(); };
      barra.appendChild(b);
    }
    barra.appendChild(estado);
    vista.appendChild(barra);
    img.onload = orientar;
    img.src = info.imagen;
    lienzo.style.cssText = 'display:block;margin:0 auto;max-width:100%;max-height:56vh;cursor:zoom-in';
    lienzo.onclick = () => window.open(info.imagen, '_blank');
    vista.appendChild(lienzo);
    orientar();
  } else if (info.enlace) {
    const frame = document.createElement('iframe');
    frame.src = info.enlace;
    frame.style.cssText = 'width:100%;height:62vh;border:0;background:#fff';
    vista.appendChild(frame);
  } else {
    vista.textContent = 'No se pudo mostrar una vista previa. Revisa el documento en el formulario (detras de esta ventana).';
  }
  if (info.enlace || info.imagen) {
    const a = document.createElement('a');
    a.href = info.enlace || info.imagen;
    a.target = '_blank';
    a.textContent = 'Abrir en otra pestaña';
    a.style.cssText = 'display:block;margin-top:8px;font-size:13px';
    vista.appendChild(a);
  }

  const ok = m.querySelector('#tm-ok');
  const soporte = m.querySelector('#tm-soporte');
  let editado = false;  // si lo escribiste tu, cambiar la opcion ya no lo reemplaza
  soporte.oninput = () => { editado = true; };
  m.querySelectorAll('input[name=tm-decision]').forEach(r => r.onchange = () => {
    ok.disabled = false; ok.style.opacity = 1;
    if (!editado) soporte.value = info.soportes[r.value] || '';
  });
  ok.onclick = () => {
    const elegido = m.querySelector('input[name=tm-decision]:checked');
    if (!elegido) return;
    window.__tumacoDecision = JSON.stringify({decision: elegido.value, soporte: soporte.value.trim(), giro});
    m.remove();
  };
}
"""

# Todas las preguntas del formulario: texto, tipo, valor actual y selector (mismo estilo que los de arriba)
_JS_INVENTARIO = r"""
(formSel) => {
  const form = document.querySelector(formSel);
  if (!form) return [];
  const ruta = el => {
    const partes = [];
    while (el && el !== form) {
      const padre = el.parentElement;
      partes.unshift(`${el.tagName.toLowerCase()}:nth-child(${[...padre.children].indexOf(el) + 1})`);
      el = padre;
    }
    return formSel + ' > ' + partes.join(' > ');
  };
  const texto = el => (el ? (el.innerText || el.textContent || '') : '').replace(/\s+/g, ' ').trim();
  return [...form.querySelectorAll('.question')].map(q => {
    const etiqueta = q.querySelector('.question-label');
    const entradas = [...q.querySelectorAll('input:not([type=hidden]), select, textarea')];
    const opciones = entradas.filter(i => i.type === 'radio' || i.type === 'checkbox');
    const archivo = entradas.find(i => i.type === 'file');
    let tipo = 'nota', valor = '';
    if (q.querySelector('canvas')) {
      tipo = 'firma'; valor = '(lienzo de firma)';
    } else if (archivo) {
      tipo = 'archivo';
      valor = texto(q.querySelector('.fake-file-input')) || archivo.getAttribute('data-loaded-file-name') || '';
    } else if (opciones.length) {
      tipo = opciones[0].type === 'radio' ? 'opcion unica' : 'opcion multiple';
      valor = opciones.filter(o => o.checked).map(o => texto(o.closest('label')) || o.value).join(' | ');
    } else if (entradas[0] && entradas[0].tagName === 'SELECT') {
      tipo = 'lista';
      valor = entradas[0].selectedOptions[0] ? texto(entradas[0].selectedOptions[0]) : '';
    } else if (entradas[0]) {
      tipo = entradas[0].tagName === 'TEXTAREA' ? 'texto largo' : (entradas[0].type || 'texto');
      valor = entradas[0].value;
    }
    return {
      pregunta: ((etiqueta && etiqueta.innerText) || '').trim().split('\n')[0].slice(0, 150),
      tipo,
      valor: (valor || '').slice(0, 200),
      selector: ruta(q),
      visible: q.offsetParent !== null,
    };
  });
}
"""

# Descarga una imagen desde la pagina (sirve para blob: y enlaces del mismo sitio) -> base64
_JS_LEER_URL = r"""
async (src) => {
  let resp;
  try { resp = await fetch(src, { credentials: 'include' }); }
  catch (e) { resp = await fetch(src); }  // otro dominio que no acepta credenciales
  if (!resp.ok) throw new Error('respuesta ' + resp.status);
  const blob = await resp.blob();
  return await new Promise(ok => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1] || null);
    r.readAsDataURL(blob);
  });
}
"""

# Ultimo recurso: copia la imagen ya cargada en la vista previa (a tamaño real) -> base64 JPG
_JS_LEER_IMG = r"""
(el) => {
  const i = el.querySelector('.file-preview img');
  if (!i || !i.complete || !i.naturalWidth) return null;
  const c = document.createElement('canvas');
  c.width = i.naturalWidth; c.height = i.naturalHeight;
  c.getContext('2d').drawImage(i, 0, 0);
  return c.toDataURL('image/jpeg', 0.95).split(',')[1];
}
"""
