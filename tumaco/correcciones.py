"""Correcciones que se aplican dentro del formulario de edicion (Enketo) de cada formulario."""
from playwright.sync_api import Locator, Page

from .humano import clic, escribir, pausa

FORM = "body > div.main > article > form"

# Campos que deben quedar en MAYUSCULA, por formulario (1 = REGISTRO DE VISITA PUERTA A PUERTA)
MAYUSCULAS = {
    1: [
        f"{FORM} > section:nth-child(4) > label:nth-child(8)",
        f"{FORM} > section:nth-child(5) > label:nth-child(2)",
        f"{FORM} > section:nth-child(5) > label:nth-child(5)",
        f"{FORM} > section:nth-child(5) > label:nth-child(6)",
        f"{FORM} > section:nth-child(10) > section.or-group.or-branch.or-appearance-field-list > label:nth-child(2)",
        f"{FORM} > section:nth-child(10) > section:nth-child(4) > label:nth-child(2)",
    ],
}

# Seccion donde se cargan los documentos anexos, por formulario
DOCUMENTOS = {
    1: f"{FORM} > section:nth-child(11)",
}

CONFIRMAR_ELIMINAR = (
    "body > div.vex.vex-theme-plain > div > form > div.vex-dialog-buttons"
    " > button.btn.btn-primary.small.vex-dialog-button.vex-first"
)


def aplicar(page: Page, numero_formulario: int) -> list[str]:
    """Aplica las correcciones del formulario y devuelve un resumen de lo que cambio."""
    cambios = []
    for selector in MAYUSCULAS.get(numero_formulario, []):
        cambio = poner_mayusculas(page, selector)
        if cambio:
            cambios.append(cambio)
    if numero_formulario in DOCUMENTOS:
        print("\nDocumentos anexos:")
        for doc in revisar_documentos(page, DOCUMENTOS[numero_formulario]):
            cambios.append(f"{doc['pregunta']}: {doc['archivo']} -> {doc['decision']}")
    return cambios


# ---------- Mayusculas ----------

def poner_mayusculas(page: Page, selector: str) -> str | None:
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
    nuevo = actual.strip().upper()
    if actual == nuevo:
        print(f"   - {nombre}: ya esta en mayuscula ({actual or 'vacio'})")
        return None

    campo.scroll_into_view_if_needed()
    pausa(page, 0.3, 0.8)
    escribir(campo, nuevo)
    campo.dispatch_event("change")  # Enketo guarda el valor al detectar el cambio
    print(f"   * {nombre}: '{actual}' -> '{nuevo}'")
    return f"{nombre}: {actual} -> {nuevo}"


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
