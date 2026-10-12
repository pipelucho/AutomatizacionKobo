"""Correcciones que se aplican dentro del formulario de edicion (Enketo) de cada formulario."""
import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError

from . import cedula, config
from .humano import clic, escribir, pausa
from .texto import norm

FORM = "body > div.main > article > form"

# Campos que deben quedar en MAYUSCULA, por formulario (1 = REGISTRO DE VISITA PUERTA A PUERTA)
MAYUSCULAS = {
    1: [
        f"{FORM} > section:nth-child(4) > label:nth-child(8)",
        f"{FORM} > section:nth-child(5) > label:nth-child(5)",
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",
    ],
    2: [
        f"{FORM} > section:nth-child(5) > label:nth-child(5)",
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",
    ],
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
}

# VERIFICACION DEL USUARIO, "la persona que atiende la visita manifiesta ser": si esta marcada
# la opcion "Otro", el usuario no se corrige ni se envia (se anota en el Excel)
OPCION_OTRO = {
    1: f"{FORM} > section:nth-child(6) > fieldset:nth-child(2) > fieldset > div > label:nth-child(9)",
}

# Seccion donde se cargan los documentos anexos, por formulario
DOCUMENTOS = {
    1: f"{FORM} > section:nth-child(11)",
}

# Firma que se borra y se vuelve a dibujar: seccion del formulario y trazos guardados en firmas/
FIRMAS = {
    1: {"seccion": f"{FORM} > section:nth-child(10) > section:nth-child(4)", "trazos": "contratista.json"},
    2: {"seccion": f"{FORM} > section:nth-child(5) > section:nth-child(18)", "trazos": "contratista.json"},  # misma firma
}

# Fotos de la cedula que se recortan al borde del documento y se enderezan: (pregunta, lado)
CEDULAS = {
    2: [
        (f"{FORM} > section:nth-child(6) > label:nth-child(2)", "cara"),
        (f"{FORM} > section:nth-child(6) > label:nth-child(3)", "reverso"),
    ],
}

CONFIRMAR_ELIMINAR = (
    "body > div.vex.vex-theme-plain > div > form > div.vex-dialog-buttons"
    " > button.btn.btn-primary.small.vex-dialog-button.vex-first"
)


@dataclass
class Resultado:
    cambios: list = field(default_factory=list)  # resumen de cada cambio hecho
    cedulas: dict = field(default_factory=dict)  # lado ('cara'/'reverso') -> jpg ajustado
    revisar: list = field(default_factory=list)  # lo que no se pudo hacer y queda para hacer a mano


def aplicar(page: Page, numero_formulario: int, usuario=None) -> Resultado:
    """Aplica las correcciones del formulario: que cambio, cedulas ajustadas y que revisar a mano.

    `usuario` (excel.Usuario) aporta los datos corregidos que se escriben tal cual en Kobo.
    """
    resultado = Resultado()
    cambios = resultado.cambios
    if usuario is not None:
        print("\nDatos del Excel:")
        for selector, atributo in VALORES_DEL_EXCEL.get(numero_formulario, []):
            valor = " ".join(str(getattr(usuario, atributo, "") or "").split()).upper()
            if not valor:
                print(f"   [!] El Excel no tiene {atributo} para este usuario; se deja el de Kobo")
                continue
            cambio = poner_valor(page, selector, valor)
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
    if numero_formulario in FIRMAS:
        firma = FIRMAS[numero_formulario]
        print("\nFirma del responsable contratista:")
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
        for doc in revisar_documentos(page, DOCUMENTOS[numero_formulario]):
            cambios.append(f"{doc['pregunta']}: {doc['archivo']} -> {doc['decision']}")
    return resultado


def tiene_correcciones(numero_formulario: int) -> bool:
    """True si el formulario ya tiene correcciones configuradas (solo entonces se envia a Kobo)."""
    return any(numero_formulario in m for m in (MAYUSCULAS, VALORES_FIJOS, VALORES_DEL_EXCEL, DOCUMENTOS, FIRMAS,
                                                 CEDULAS))


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


# ---------- Campos de texto ----------

def poner_mayusculas(page: Page, selector: str) -> str | None:
    return _corregir_texto(page, selector, lambda actual: actual.strip().upper(), "ya esta en mayuscula")


def poner_valor(page: Page, selector: str, valor: str) -> str | None:
    return _corregir_texto(page, selector, lambda _: valor, "ya tiene el valor correcto")


def _corregir_texto(page: Page, selector: str, transformar, msg_sin_cambio: str) -> str | None:
    """Reescribe el campo con transformar(valor_actual) si el resultado es distinto."""
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
    escribir(campo, nuevo)
    campo.dispatch_event("change")  # Enketo guarda el valor al detectar el cambio
    print(f"   * {nombre}: '{actual}' -> '{nuevo}'")
    return f"{nombre}: {actual} -> {nuevo}"


# ---------- Firma ----------

def rehacer_firma(page: Page, selector_seccion: str, archivo_trazos: str) -> bool:
    """Borra la firma del lienzo (boton del pie + Aceptar) y la dibuja de nuevo con el mouse."""
    ruta = config.FIRMAS_DIR / archivo_trazos
    if not ruta.exists():
        print(f"   [!] No existe {ruta}; crea los trazos con herramientas/firma_desde_imagen.py")
        return False
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

    for trazo in firma["trazos"]:
        page.mouse.move(*punto(trazo[0]))
        page.mouse.down()
        for p in trazo[1:]:
            page.mouse.move(*punto(p))
        page.mouse.up()
        pausa(page, 0.01, 0.04)
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
        return None, None, f"no se encontro el borde de la cedula {lado} en la foto"
    ajustada, seguro, nota = resultado
    if not seguro:
        (carpeta / f"{prefijo}_dudosa.jpg").write_bytes(cedula.a_jpg(ajustada))
        return None, None, f"no es seguro hacia donde va arriba la cedula {lado}"

    jpg = cedula.a_jpg(ajustada)
    (carpeta / f"{prefijo}_ajustada.jpg").write_bytes(jpg)
    nombre = f"{Path(info['archivo']).stem}-ajustada.jpg"
    if not reemplazar_archivo(page, pregunta, nombre, jpg):
        return None, None, f"no se pudo subir la cedula {lado} ajustada"
    print(f"   * Cedula {lado}: recortada y enderezada ({nota})")
    return f"Cedula {lado}: {info['archivo']} -> {nombre}", jpg, None


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
        page.evaluate(_JS_MODAL, info)
        page.wait_for_function("() => window.__tumacoDecision", timeout=0, polling=500)
        decision = page.evaluate("() => { const d = window.__tumacoDecision; delete window.__tumacoDecision; return d; }")

        if decision == "eliminar":
            eliminar_documento(page, pregunta)
            print(f"   * {info['pregunta']}: ELIMINADO ({info['archivo']})")
        else:
            print(f"   - {info['pregunta']}: se conserva ({info['archivo']})")
        resultados.append({"pregunta": info["pregunta"], "archivo": info["archivo"], "decision": decision})
    return resultados


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
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#tm-pregunta').textContent = info.pregunta;
  m.querySelector('#tm-archivo').textContent = info.archivo;

  const vista = m.querySelector('#tm-vista');
  if (info.imagen) {
    const img = document.createElement('img');
    img.src = info.imagen;
    img.style.cssText = 'max-width:100%;max-height:62vh;cursor:zoom-in';
    img.onclick = () => window.open(info.imagen, '_blank');
    vista.appendChild(img);
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
  m.querySelectorAll('input[name=tm-decision]').forEach(r => r.onchange = () => { ok.disabled = false; ok.style.opacity = 1; });
  ok.onclick = () => {
    const elegido = m.querySelector('input[name=tm-decision]:checked');
    if (!elegido) return;
    window.__tumacoDecision = elegido.value;
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
