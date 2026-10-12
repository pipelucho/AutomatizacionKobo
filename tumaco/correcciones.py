"""Correcciones que se aplican dentro del formulario de edicion (Enketo) de cada formulario."""
import json
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError

from . import config
from .humano import clic, escribir, pausa
from .texto import norm

FORM = "body > div.main > article > form"

# Campos que deben quedar en MAYUSCULA, por formulario (1 = REGISTRO DE VISITA PUERTA A PUERTA)
MAYUSCULAS = {
    1: [
        f"{FORM} > section:nth-child(4) > label:nth-child(8)",
        f"{FORM} > section:nth-child(5) > label:nth-child(5)",
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",
        f"{FORM} > section:nth-child(10) > section.or-group.or-branch.or-appearance-field-list > label:nth-child(2)",
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

CONFIRMAR_ELIMINAR = (
    "body > div.vex.vex-theme-plain > div > form > div.vex-dialog-buttons"
    " > button.btn.btn-primary.small.vex-dialog-button.vex-first"
)


def aplicar(page: Page, numero_formulario: int, usuario=None) -> list[str]:
    """Aplica las correcciones del formulario y devuelve un resumen de lo que cambio.

    `usuario` (excel.Usuario) aporta los datos corregidos que se escriben tal cual en Kobo.
    """
    cambios = []
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
    if numero_formulario in DOCUMENTOS:
        print("\nDocumentos anexos:")
        for doc in revisar_documentos(page, DOCUMENTOS[numero_formulario]):
            cambios.append(f"{doc['pregunta']}: {doc['archivo']} -> {doc['decision']}")
    return cambios


def tiene_correcciones(numero_formulario: int) -> bool:
    """True si el formulario ya tiene correcciones configuradas (solo entonces se envia a Kobo)."""
    return any(numero_formulario in m for m in (MAYUSCULAS, VALORES_FIJOS, VALORES_DEL_EXCEL, DOCUMENTOS, FIRMAS))


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
    pausa(page, 0.5, 1.0)

    # 1. Borrar la firma actual
    clic(pregunta.locator("div.draw-widget__footer > button").first)
    confirmar = page.locator(CONFIRMAR_ELIMINAR)
    try:
        confirmar.wait_for(timeout=5_000)
        pausa(page, 0.3, 0.7)
        clic(confirmar)
        confirmar.wait_for(state="detached", timeout=10_000)
        print("   - Firma anterior borrada")
    except TimeoutError:
        print("   - No habia firma para borrar")

    # 2. Dibujarla centrada en el lienzo, ocupando hasta el 80% del espacio
    lienzo.evaluate("el => el.scrollIntoView({block: 'center'})")
    pausa(page, 0.4, 0.8)
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
            page.mouse.move(*punto(p), steps=3)
        page.mouse.up()
        pausa(page, 0.05, 0.2)
    pausa(page, 0.8, 1.2)
    print(f"   * Firma dibujada ({len(firma['trazos'])} trazos)")
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
        if not info["archivo"]:
            print(f"   - {info['pregunta']}: sin documento cargado")
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
  const img = label.querySelector('.file-preview img');
  const enlace = label.querySelector('a.btn-download[href], .file-feedback a[href], a[download][href]');
  const archivo = texto(label.querySelector('.fake-file-input'))
    || (input && input.getAttribute('data-loaded-file-name'))
    || (img || enlace ? 'documento cargado' : '');
  return {
    pregunta: texto(label.querySelector('.question-label')) || 'Documento',
    archivo,
    imagen: img ? img.src : null,
    enlace: enlace && enlace.getAttribute('href') !== '#' ? enlace.href : null,
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
