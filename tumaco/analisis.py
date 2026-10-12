"""Analisis de lo ya enviado a Kobo con las reglas de nombre y casa (tumaco.reglas). Solo lee.

Para cada persona y formulario enviado:
1. Ubica su envio en Kobo (API) por documento y No. de usuario.
2. Toma el nombre y la direccion ORIGINALES: de los logs de las corridas (antes de que el bot los
   cambiara) o, si no hay log, los actuales de Kobo.
3. Decide con Kobo + Excel + hoja que deberia quedar y lista solo los campos que no coinciden.
El resultado (salida/analisis_correcciones.json) lo usa herramientas/corregir.py.
"""
import json
import re
from pathlib import Path

from . import config, excel, reglas, sheets
from .texto import mismo_documento, norm, numeros_casa, similitud_nombre

ANALISIS_PATH = config.OUTPUT_DIR / "analisis_correcciones.json"

# Campos de cada formulario en la API de Kobo
CAMPOS = {
    1: {"nombre": "grp_datos_persona_atendida/nombre_persona_atendida",
        "nombre_firma": "group_ma5xk12/grp_firma_persona_atendida/persona_atendida_nombre_firma",
        "documento": "grp_datos_persona_atendida/documento_persona_atendida",
        "usuario": "grp_datos_persona_atendida/no_usuario",
        "direccion": "grp_datos_persona_atendida/direccion"},
    2: {"nombre": "grp_declaracion/nombre_usuario_decl",
        "nombre_firma": "grp_declaracion/grp_firma_usuario/usuario_nombre_firma",
        "documento": "grp_declaracion/documento_usuario_decl",
        "usuario": "",  # se busca en el formulario (pregunta 'No. Usuario')
        "direccion": "grp_declaracion/direccion_usuario_decl"},
    3: {"nombre": "datos_usuario/nombre",
        "nombre_firma": "declaracion_aceptacion/entrevistado/entrevistado_nombre",
        "documento": "datos_usuario/documento",
        "usuario": "datos_usuario/no_usuario",
        "direccion": "datos_usuario/direccion"},
    4: {"nombre": "grp_usuario_inmueble/nombre_usuario",
        "nombre_firma": "grp_declaracion/grp_firma_usuario/firma_usuario_nombre",
        "documento": "grp_usuario_inmueble/documento_usuario",
        "usuario": "grp_usuario_inmueble/no_usuario",
        "direccion": "grp_usuario_inmueble/direccion"},
}


# ---------- Kobo (API) ----------

def descargar_envios(request) -> dict[int, dict]:
    """{formulario: {"uid": ..., "campos": {...}, "envios": [...]}} con todos los envios de los 4 formularios."""
    base = config.KOBO_URL
    activos = request.get(f"{base}/api/v2/assets/", params={"format": "json", "q": "asset_type:survey",
                                                             "limit": "100"}).json()["results"]
    salida = {}
    for n, nombre in enumerate(config.FORMULARIOS, start=1):
        uid = next(a["uid"] for a in activos if norm(a["name"]).startswith(norm(nombre)[:20]))
        campos = dict(CAMPOS[n])
        if not campos["usuario"]:
            survey = request.get(f"{base}/api/v2/assets/{uid}/", params={"format": "json"}).json()["content"]["survey"]
            campos["usuario"] = next((s["$xpath"] for s in survey
                                      if norm((s.get("label") or [""])[0]) == "no. usuario"), "")
        pedir = ["_id", "_submission_time", *[x for x in campos.values() if x]]
        datos = request.get(f"{base}/api/v2/assets/{uid}/data/",
                            params={"format": "json", "limit": "30000", "fields": json.dumps(pedir)}).json()
        salida[n] = {"uid": uid, "campos": campos, "envios": datos["results"]}
        print(f"   Formulario {n}: {len(datos['results'])} envio(s)")
    return salida


def buscar_envio(envios: list[dict], campos: dict, usuario: excel.Usuario) -> tuple[dict | None, str, list[dict]]:
    """(envio de la persona, nota, ajenos).

    Misma regla que el bot (Coincidencia.confirmada): nombre parecido y ademas usuario, casa o documento;
    o dos de esos tres. 'ajenos' son registros con el mismo nombre que NO son de la persona: el bot
    pudo haberlos editado por error cuando aceptaba un registro solo por el nombre.
    """
    def val(e, k):
        return str(e.get(campos[k], "") or "") if campos.get(k) else ""

    nombres = {n for n in (usuario.nombre, usuario.nombre_final) if n}

    def evaluar(e):
        doc_ok = bool(usuario.documento) and mismo_documento(usuario.documento, val(e, "documento"))
        usu_ok = re.sub(r"\D", "", val(e, "usuario")) == usuario.usuario
        casa_ok = bool(usuario.casa) and bool(numeros_casa(usuario.casa) & numeros_casa(val(e, "direccion")))
        sim = max(similitud_nombre(n, val(e, "nombre")) for n in nombres)
        valido = ((sim >= 0.6 and (usu_ok or casa_ok or doc_ok)) or (usu_ok and casa_ok)
                  or (doc_ok and (usu_ok or casa_ok)))
        return valido, (doc_ok + usu_ok + casa_ok, sim)

    evaluados = [(e, *evaluar(e)) for e in envios]
    validos = sorted(((e, puntos) for e, valido, puntos in evaluados if valido), key=lambda x: x[1], reverse=True)
    mismo_nombre = {reglas.limpio(n) for n in nombres}
    ajenos = [e for e, valido, _ in evaluados if not valido and reglas.limpio(val(e, "nombre")) in mismo_nombre]
    if not validos:
        return None, "ningun registro de Kobo coincide por usuario, casa o documento", ajenos
    nota = ""
    # Duplicado de verdad: otro registro con el mismo usuario o documento (no basta un vecino con el mismo
    # apellido y la misma casa, como Biani y Evangelista Portocarrero en la casa 27)
    otros = [e for e, _ in validos[1:]
             if re.sub(r"\D", "", val(e, "usuario")) == usuario.usuario
             or (usuario.documento and mismo_documento(usuario.documento, val(e, "documento")))]
    if otros:
        nota = ("hay otro registro que tambien coincide (posible duplicado): "
                + "; ".join(_describir(e, campos) for e in otros[:3]))
    return validos[0][0], nota, ajenos


def _describir(e: dict, campos: dict) -> str:
    v = lambda k: str(e.get(campos[k], "") or "").strip() if campos.get(k) else ""  # noqa: E731
    return f"_id {e['_id']}: {v('nombre')}, usuario {v('usuario') or '-'}, {v('direccion') or '-'}, doc {v('documento') or '-'}"


# ---------- Valores originales (logs) ----------

_USUARIO = re.compile(r"^\[\d+/\d+\] (?:Usuario: )?.*\| USUARIO (\S+)")
_REHACER = re.compile(r"^\[\d+/\d+\] .*\| USUARIO (\S+) \(fila")
_FORM = re.compile(r"^--- Formulario (\d):")
_CAMBIO = re.compile(r"^\s+\* (DIRECCI[ÓO]N|NOMBRE[^:]*): '(.*)' -> '(.*)'$")
# Campo que no se cambio porque ya estaba bien: su valor tambien es el original
_SIN_CAMBIO = re.compile(r"^\s+- (DIRECCI[ÓO]N|NOMBRE[^:]*): [^(]*\((.*)\)$")


def originales_de_logs() -> dict[tuple[str, int], dict]:
    """{(usuario, formulario): {"direccion": original, "nombres": [original 1, original 2]}} del log mas antiguo."""
    originales = {}
    for log in sorted((config.OUTPUT_DIR / "logs").glob("*.log")):
        usuario = numero = None
        seccion = ""
        for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if m := (_USUARIO.match(linea) or _REHACER.match(linea)):
                usuario, numero = m.group(1), None
            elif m := _FORM.match(linea):
                numero = int(m.group(1))
            elif linea.rstrip().endswith(":") and not linea.startswith(" "):
                seccion = linea.strip()
            elif usuario and numero and (m := _CAMBIO.match(linea) or _SIN_CAMBIO.match(linea)):
                datos = originales.setdefault((usuario, numero), {"direccion": None, "nombres": [], "log": log.name})
                if datos["log"] != log.name:  # ya se tomo de un log anterior (el original es el primero)
                    continue
                if m.group(1).startswith("DIRECCI") and datos["direccion"] is None:
                    datos["direccion"] = m.group(2)
                elif m.group(1).startswith("NOMBRE") and seccion.startswith("Datos del Excel") and len(datos["nombres"]) < 2:
                    datos["nombres"].append(m.group(2))
    return originales


# ---------- Analisis ----------

def analizar(tabla, envios: dict, filas_hoja) -> dict:
    refs = sheets.referencias(filas_hoja)
    originales = originales_de_logs()
    personas = []
    for u in excel.usuarios(tabla):
        ref = refs.get(u.usuario, {})
        u.ref_nombre, u.ref_direccion = ref.get("nombre", ""), ref.get("direccion", "")
        formularios, avisos, sin_registro = [], [], []
        nombre_final = casa_final = ""
        for n in sorted(excel.COLUMNA_FORMULARIO):
            if not excel.fue_enviado(u.marca(n)):
                continue
            info = envios[n]
            u.nombre_final = nombre_final or u.nombre_final  # el de la persona segun el formulario 1
            envio, nota, ajenos = buscar_envio(info["envios"], info["campos"], u)
            for e in ajenos:
                avisos.append(f"F{n}: registro de OTRA persona con el mismo nombre, que el bot pudo editar por "
                              f"error ({_describir(e, info['campos'])})")
            if not envio:
                avisos.append(f"F{n}: marcado como enviado en el Excel, pero {nota}")
                sin_registro.append(n)
                continue
            orig = originales.get((u.usuario, n), {})
            correcciones = {}

            def revisar(campo, original, nuevo, aviso, tipo):
                xpath = info["campos"][campo]
                actual = str(envio.get(xpath, "") or "")
                if reglas.limpio(actual) != reglas.limpio(nuevo):
                    correcciones[xpath] = {"campo": campo, "actual": actual, "nuevo": nuevo,
                                           "original": original}
                if aviso:
                    avisos.append(f"F{n} {tipo}: {aviso}")

            # Casa
            dir_actual = str(envio.get(info["campos"]["direccion"], "") or "")
            dir_original = orig.get("direccion") if orig.get("direccion") is not None else dir_actual
            dir_nueva, aviso = reglas.decidir_casa(dir_original, u.casa, u.ref_direccion)
            revisar("direccion", dir_original, dir_nueva, aviso, "casa")
            # Nombres (el de la persona y el de su firma)
            nombres_orig = orig.get("nombres", [])
            for i, campo in enumerate(("nombre", "nombre_firma")):
                actual = str(envio.get(info["campos"][campo], "") or "")
                original = nombres_orig[i] if i < len(nombres_orig) else actual
                # En los formularios 2 a 4 se compara con el nombre decidido en el 1 (si fue otra persona)
                nuevo, aviso = reglas.decidir_nombre(original, nombre_final or u.nombre, u.ref_nombre)
                revisar(campo, original, nuevo, aviso if i == 0 else None, "nombre")
                if i == 0 and n == 1 and aviso:
                    nombre_final = nuevo
            if nota:
                avisos.append(f"F{n}: {nota}")
            if n == 1:
                casa_final = reglas.casa_corta(dir_nueva)
                if not orig and u.propietario.lower() == "no" and reglas.limpio(envio.get(info["campos"]["nombre"], "")) == reglas.limpio(u.nombre):
                    avisos.append("F1 nombre: no hay registro del nombre original y quien atendio no es propietario: "
                                  "verificar que el nombre del Excel sea el de quien firmo")
            # El bot siempre deja el nombre en mayuscula: si no lo esta, este registro nunca lo proceso (proceso
            # otro por error) y hay que rehacer el formulario completo, no solo parchar campos
            nombre_kobo = str(envio.get(info["campos"]["nombre"], "") or "")
            rehacer = bool(nombre_kobo.strip()) and nombre_kobo.strip() != nombre_kobo.strip().upper()
            if rehacer:
                avisos.append(f"F{n}: su registro ({_describir(envio, info['campos'])}) nunca fue corregido por el "
                              f"bot: el formulario se rehace completo")
            formularios.append({"formulario": n, "uid": info["uid"], "_id": envio["_id"], "nota": nota,
                                "con_log": bool(orig), "rehacer": rehacer, "correcciones": correcciones})

        # Hoja de Google: lo que deberia tener la fila si ya se lleno
        hoja = {}
        fila_hoja = sheets.buscar_fila(filas_hoja, u.usuario) if u.hoja else None
        if fila_hoja:
            u.nombre_final, u.casa_final = nombre_final, casa_final or u.casa_final
            esperado = sheets.valores_usuario(u, sheets._celda(filas_hoja, fila_hoja, sheets.COL_DIRECCION_INICIAL))
            for col in (sheets.COL_NOMBRE, sheets.COL_DIRECCION):
                actual = sheets._celda(filas_hoja, fila_hoja, col)
                if reglas.limpio(actual) != reglas.limpio(esperado[col]):
                    hoja[f"{col}{fila_hoja}"] = {"actual": actual, "nuevo": esperado[col]}

        if any(f["correcciones"] for f in formularios) or hoja or avisos:
            personas.append({"usuario": u.usuario, "fila": u.fila, "nombre": u.nombre,
                             "nombre_final": nombre_final, "casa_final": casa_final,
                             "formularios": [f for f in formularios if f["correcciones"] or f["rehacer"]],
                             "hoja": hoja, "avisos": avisos, "sin_registro": sin_registro})
    resultado = {"personas": personas}
    ANALISIS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANALISIS_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultado


def resumen(resultado: dict) -> str:
    lineas = []
    for p in resultado["personas"]:
        lineas.append(f"\n{p['usuario']} {p['nombre']} (fila {p['fila']})")
        for f in p["formularios"]:
            if f["rehacer"]:
                lineas.append(f"   F{f['formulario']}: REHACER COMPLETO (el bot proceso otro registro)")
                continue
            fuente = "valor original del log" if f["con_log"] else "sin log: valor actual de Kobo"
            for c in f["correcciones"].values():
                lineas.append(f"   F{f['formulario']} {c['campo']}: '{c['actual']}' -> '{c['nuevo']}'  ({fuente})")
        for n in p.get("sin_registro", []):
            lineas.append(f"   F{n}: REHACER (sin registro propio en Kobo: quedara 'No encontrado' y se quita su PDF)")
        for celda, c in p["hoja"].items():
            lineas.append(f"   Hoja {celda}: '{c['actual']}' -> '{c['nuevo']}'")
        for a in p["avisos"]:
            lineas.append(f"   [verificar] {a}")
    parches = [f for p in resultado["personas"] for f in p["formularios"] if not f["rehacer"]]
    rehacer = sum(1 for p in resultado["personas"] for f in p["formularios"] if f["rehacer"]) + \
        sum(len(p.get("sin_registro", [])) for p in resultado["personas"])
    n_campos = sum(len(f["correcciones"]) for f in parches)
    n_hoja = sum(len(p["hoja"]) for p in resultado["personas"])
    lineas.append(f"\nTotal: {n_campos} campo(s) a parchar en {len(parches)} formulario(s), {rehacer} formulario(s) a "
                  f"rehacer y {n_hoja} celda(s) de la hoja. Detalle en {ANALISIS_PATH}")
    return "\n".join(lineas)
