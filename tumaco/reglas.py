"""Como decidir el nombre y la casa cuando Kobo, el Excel de usuarios y la hoja de Google no coinciden.

Las tres fuentes:
- Kobo: lo que quedo en el formulario (quien atendio, firmo y de quien es la cedula).
- Excel de usuarios: nombre (A) y casa (C).
- Hoja de Google 'Tumaco': nombre inicial (B) y direccion inicial (E) del usuario.

Nombre: si Kobo se parece al Excel (errores de digitacion, ej. Diolinda/Biolinda) se corrige con el Excel.
Si es otra persona, se deja el de Kobo: cambiarlo dejaria el nombre de una persona con la cedula y la
firma de otra. Se avisa para verificar.
Casa: se cambia solo si dos fuentes coinciden; si no, se deja la de Kobo y se avisa para verificar.
"""
import re

from .texto import numeros_casa, similitud_nombre

UMBRAL_MISMO_NOMBRE = 0.75  # desde aqui las diferencias se toman como errores de digitacion


def limpio(texto: str) -> str:
    return " ".join(str(texto or "").split()).upper()


def decidir_nombre(kobo: str, excel: str, hoja: str = "") -> tuple[str, str | None]:
    """(nombre que debe quedar, aviso para verificar o None)."""
    kobo, excel, hoja = limpio(kobo), limpio(excel), limpio(hoja)
    if not excel:
        return kobo, None
    if not kobo or similitud_nombre(kobo, excel) >= UMBRAL_MISMO_NOMBRE:
        return excel, None
    if hoja and similitud_nombre(kobo, hoja) >= UMBRAL_MISMO_NOMBRE:
        motivo = "el Excel tiene otro nombre; Kobo coincide con la hoja"
    elif hoja and similitud_nombre(excel, hoja) >= UMBRAL_MISMO_NOMBRE:
        motivo = "quien atendio es otra persona; el Excel y la hoja tienen al usuario inicial"
    else:
        motivo = "Kobo, Excel y hoja tienen nombres distintos"
    return kobo, f"se deja '{kobo}' de Kobo ({motivo}). Excel: '{excel}', hoja: '{hoja or '-'}'"


def normalizar_direccion(texto: str) -> str:
    """Mayuscula, espacios simples y CS -> CASA ('Cs652' -> 'CASA 652')."""
    return re.sub(r"\bCS\.?\s*(?=\d)", "CASA ", limpio(texto))


def decidir_casa(kobo: str, casa_excel: str, direccion_hoja: str = "") -> tuple[str, str | None]:
    """(direccion que debe quedar, aviso para verificar o None).

    - El numero de Kobo coincide con el Excel: se deja (en mayuscula).
    - Kobo sin numero ('No tiene numero la casa'): CASA <Excel> si la hoja coincide o no tiene dato.
    - Kobo con otro numero: CASA <Excel> solo si la hoja coincide con el Excel; si la hoja coincide
      con Kobo, el error esta en el Excel y se deja Kobo.
    - Si no hay dos fuentes de acuerdo, no se cambia y se avisa.
    """
    actual = normalizar_direccion(kobo)
    casa_excel = limpio(casa_excel)
    if not casa_excel:
        return actual, None
    k, e, s = numeros_casa(actual), numeros_casa(casa_excel), numeros_casa(direccion_hoja)
    nueva = f"CASA {casa_excel}"
    if k & e:
        return actual, None
    if not k:
        if not s or e & s:
            return nueva, None
        return actual, (f"Kobo sin numero ('{actual}') y el Excel ({casa_excel}) no coincide con la hoja "
                        f"('{direccion_hoja}'); no se cambia")
    if s and k & s:
        return actual, f"se deja '{actual}' de Kobo (coincide con la hoja '{direccion_hoja}'); el Excel dice {casa_excel}"
    if s and e & s:
        return nueva, None
    return actual, (f"Kobo '{actual}', Excel {casa_excel} y hoja '{direccion_hoja or '-'}' no coinciden; "
                    f"no se cambia")


def casa_corta(texto: str) -> str:
    """'CASA 298 SECTOR 1' -> 'CASA 298'; 'CASA 317 A LA LIBERTAD' -> 'CASA 317 A'."""
    m = re.search(r"\bCASA\s*(\d+)(?:\s?([A-Z])(?![A-Z0-9]))?", normalizar_direccion(texto))
    return f"CASA {m.group(1)}" + (f" {m.group(2)}" if m.group(2) else "") if m else ""


# Columna J de la hoja (justificacion / soporte): texto por defecto segun el documento anexo del formulario 1.
# En la ventana del documento se puede cambiar por el soporte real (queda en la columna N del Excel).
SOPORTE_CON_ANEXO = "CEDULA DE CIUDADANIA Y RECIBO DE ENERGIA"
SOPORTE_SIN_ANEXO = "CEDULA DE CIUDADANIA"
