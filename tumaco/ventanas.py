"""Ventana sobre la pagina para revisar cambios antes de aplicarlos: cada cambio con su casilla (aplicar o no)
y su valor nuevo editable, mas el contexto para decidir (Excel, hoja, valor original en Kobo, motivo)."""
import json

from playwright.sync_api import Page


def revisar_cambios(page: Page, titulo: str, contexto: list[str], cambios: list[dict],
                    aplicar: str = "Aplicar los marcados", omitir: str = "No cambiar nada") -> dict[str, str] | None:
    """Muestra la ventana y espera la decision.

    cambios: [{"id", "campo", "actual", "nuevo", "detalle", "editable": True}]
    Devuelve {id: valor final} de los cambios marcados, o None si se eligio no cambiar nada.
    """
    page.bring_to_front()
    page.evaluate(_JS_VENTANA, {"titulo": titulo, "contexto": contexto, "cambios": cambios,
                                "aplicar": aplicar, "omitir": omitir})
    page.wait_for_function("() => window.__tumacoRevision", timeout=0, polling=500)
    r = json.loads(page.evaluate("() => { const r = window.__tumacoRevision; delete window.__tumacoRevision; return r; }"))
    return r["cambios"] if r["accion"] == "aplicar" else None


def escribir_texto(page: Page, titulo: str, contexto: list[str], imagen: str | None, etiqueta: str,
                   valor: str) -> tuple[str, str]:
    """Muestra una imagen (data URL) y un campo de texto. Devuelve (accion, texto):
    accion = 'guardar', 'igual' (dejar como esta) o 'terminar' (cortar el recorrido)."""
    page.bring_to_front()
    page.evaluate(_JS_TEXTO, {"titulo": titulo, "contexto": contexto, "imagen": imagen, "etiqueta": etiqueta,
                              "valor": valor})
    page.wait_for_function("() => window.__tumacoTexto", timeout=0, polling=400)
    r = json.loads(page.evaluate("() => { const r = window.__tumacoTexto; delete window.__tumacoTexto; return r; }"))
    return r["accion"], r["texto"]


_JS_TEXTO = r"""
(info) => {
  document.getElementById('tumaco-texto')?.remove();
  const m = document.createElement('div');
  m.id = 'tumaco-texto';
  m.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif">
      <div style="background:#fff;border-radius:10px;width:94vw;max-width:1100px;max-height:94vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)">
        <div style="padding:14px 18px;border-bottom:1px solid #ddd">
          <div id="tt-titulo" style="font-size:18px;font-weight:bold;color:#222"></div>
          <ul id="tt-contexto" style="margin:8px 0 0 18px;padding:0;font-size:13px;color:#444;line-height:1.5"></ul>
        </div>
        <div id="tt-vista" style="flex:1;overflow:auto;padding:10px;text-align:center;background:#f2f2f2;min-height:160px"></div>
        <div style="padding:12px 18px;border-top:1px solid #ddd">
          <label id="tt-etiqueta" style="font-size:14px;color:#333"></label>
          <input id="tt-valor" type="text" style="display:block;width:100%;margin:6px 0 12px;padding:9px;font-size:16px;border:1px solid #bbb;border-radius:4px;box-sizing:border-box">
          <div style="display:flex;gap:10px;justify-content:flex-end">
            <button data-accion="terminar" type="button" style="padding:10px 16px;font-size:15px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer;margin-right:auto">Terminar aquí</button>
            <button data-accion="igual" type="button" style="padding:10px 16px;font-size:15px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer">Dejar igual</button>
            <button data-accion="guardar" type="button" style="padding:10px 18px;font-size:15px;border-radius:6px;border:1px solid #1976d2;background:#1976d2;color:#fff;cursor:pointer">Guardar</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#tt-titulo').textContent = info.titulo;
  for (const linea of info.contexto) {
    const li = document.createElement('li'); li.textContent = linea; m.querySelector('#tt-contexto').appendChild(li);
  }
  const vista = m.querySelector('#tt-vista');
  if (info.imagen) {
    const img = document.createElement('img');
    img.src = info.imagen;
    img.style.cssText = 'max-width:100%;max-height:58vh;cursor:zoom-in';
    img.onclick = () => window.open(info.imagen, '_blank');
    vista.appendChild(img);
  } else {
    vista.textContent = 'No se pudo mostrar el documento.';
  }
  m.querySelector('#tt-etiqueta').textContent = info.etiqueta;
  const entrada = m.querySelector('#tt-valor');
  entrada.value = info.valor;
  entrada.focus();
  const responder = (accion) => { window.__tumacoTexto = JSON.stringify({accion, texto: entrada.value.trim()}); m.remove(); };
  m.querySelectorAll('button[data-accion]').forEach(b => b.onclick = () => responder(b.dataset.accion));
  entrada.onkeydown = (e) => { if (e.key === 'Enter') responder('guardar'); };
}
"""


def elegir(page: Page, titulo: str, contexto: list[str], columnas: list[str], opciones: list[list[str]],
           ninguno: str = "Ninguno es la persona") -> int | None:
    """Muestra las opciones en una tabla para elegir una. Devuelve su posicion, o None si 'Ninguno'."""
    page.bring_to_front()
    page.evaluate(_JS_ELEGIR, {"titulo": titulo, "contexto": contexto, "columnas": columnas,
                               "opciones": opciones, "ninguno": ninguno})
    page.wait_for_function("() => window.__tumacoEleccion !== undefined", timeout=0, polling=500)
    r = page.evaluate("() => { const r = window.__tumacoEleccion; delete window.__tumacoEleccion; return r; }")
    return None if r is None or r < 0 else int(r)


_JS_ELEGIR = r"""
(info) => {
  document.getElementById('tumaco-eleccion')?.remove();
  const m = document.createElement('div');
  m.id = 'tumaco-eleccion';
  m.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif">
      <div style="background:#fff;border-radius:10px;width:95vw;max-width:1250px;max-height:92vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)">
        <div style="padding:14px 18px;border-bottom:1px solid #ddd">
          <div id="te-titulo" style="font-size:18px;font-weight:bold;color:#222"></div>
          <ul id="te-contexto" style="margin:8px 0 0 18px;padding:0;font-size:13px;color:#444;line-height:1.5"></ul>
        </div>
        <div style="flex:1;overflow:auto;padding:10px 18px">
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead><tr id="te-cabeza" style="text-align:left;color:#666;font-size:12px"><th style="padding:6px"></th></tr></thead>
            <tbody id="te-filas"></tbody>
          </table>
        </div>
        <div style="padding:12px 18px;border-top:1px solid #ddd;display:flex;justify-content:flex-end">
          <button id="te-ninguno" type="button" style="padding:10px 18px;font-size:15px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer"></button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#te-titulo').textContent = info.titulo;
  for (const linea of info.contexto) {
    const li = document.createElement('li'); li.textContent = linea; m.querySelector('#te-contexto').appendChild(li);
  }
  for (const c of info.columnas) {
    const th = document.createElement('th'); th.style.padding = '6px'; th.textContent = c; m.querySelector('#te-cabeza').appendChild(th);
  }
  const responder = (i) => { window.__tumacoEleccion = i; m.remove(); };
  info.opciones.forEach((fila, i) => {
    const tr = document.createElement('tr');
    tr.style.borderTop = '1px solid #eee';
    const td = document.createElement('td');
    td.style.padding = '8px 6px';
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = 'Es este';
    b.style.cssText = 'padding:7px 14px;font-size:14px;border-radius:6px;border:1px solid #1976d2;background:#1976d2;color:#fff;cursor:pointer';
    b.onclick = () => responder(i);
    td.appendChild(b);
    tr.appendChild(td);
    for (const valor of fila) {
      const celda = document.createElement('td');
      celda.style.cssText = 'padding:8px 6px;vertical-align:top';
      celda.textContent = valor || '-';
      tr.appendChild(celda);
    }
    m.querySelector('#te-filas').appendChild(tr);
  });
  const ninguno = m.querySelector('#te-ninguno');
  ninguno.textContent = info.ninguno;
  ninguno.onclick = () => responder(-1);
}
"""


_JS_VENTANA = r"""
(info) => {
  document.getElementById('tumaco-revision')?.remove();
  const m = document.createElement('div');
  m.id = 'tumaco-revision';
  m.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:Arial,sans-serif">
      <div style="background:#fff;border-radius:10px;width:94vw;max-width:1150px;max-height:92vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)">
        <div style="padding:14px 18px;border-bottom:1px solid #ddd">
          <div id="tr-titulo" style="font-size:18px;font-weight:bold;color:#222"></div>
          <ul id="tr-contexto" style="margin:8px 0 0 18px;padding:0;font-size:13px;color:#444;line-height:1.5"></ul>
        </div>
        <div style="flex:1;overflow:auto;padding:10px 18px">
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead><tr style="text-align:left;color:#666;font-size:12px">
              <th style="padding:6px">Aplicar</th><th style="padding:6px">Campo</th>
              <th style="padding:6px">Hoy</th><th style="padding:6px">Queda (puedes editarlo)</th></tr></thead>
            <tbody id="tr-filas"></tbody>
          </table>
        </div>
        <div style="padding:12px 18px;border-top:1px solid #ddd;display:flex;gap:10px;justify-content:flex-end">
          <button id="tr-omitir" type="button" style="padding:10px 18px;font-size:15px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer"></button>
          <button id="tr-aplicar" type="button" style="padding:10px 18px;font-size:15px;border-radius:6px;border:1px solid #1976d2;background:#1976d2;color:#fff;cursor:pointer"></button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(m);
  m.querySelector('#tr-titulo').textContent = info.titulo;
  const ctx = m.querySelector('#tr-contexto');
  for (const linea of info.contexto) {
    const li = document.createElement('li');
    li.textContent = linea;
    ctx.appendChild(li);
  }
  const cuerpo = m.querySelector('#tr-filas');
  for (const c of info.cambios) {
    const tr = document.createElement('tr');
    tr.style.borderTop = '1px solid #eee';
    tr.innerHTML = `<td style="padding:8px 6px;vertical-align:top"><input type="checkbox" checked style="width:18px;height:18px"></td>
      <td style="padding:8px 6px;vertical-align:top;font-weight:bold"></td>
      <td style="padding:8px 6px;vertical-align:top;color:#b71c1c;text-decoration:line-through"></td>
      <td style="padding:8px 6px;vertical-align:top"><input type="text" style="width:100%;padding:6px;font-size:14px;border:1px solid #bbb;border-radius:4px">
        <div style="font-size:12px;color:#666;margin-top:4px"></div></td>`;
    tr.dataset.id = c.id;
    tr.children[1].textContent = c.campo;
    tr.children[2].textContent = c.actual || '(vacío)';
    const entrada = tr.querySelector('input[type=text]');
    entrada.value = c.nuevo;
    entrada.readOnly = c.editable === false;
    if (entrada.readOnly) entrada.style.background = '#f4f4f4';
    tr.querySelector('div').textContent = c.detalle || '';
    cuerpo.appendChild(tr);
  }
  const responder = (accion) => {
    const cambios = {};
    for (const tr of cuerpo.children) {
      if (tr.querySelector('input[type=checkbox]').checked) cambios[tr.dataset.id] = tr.querySelector('input[type=text]').value;
    }
    window.__tumacoRevision = JSON.stringify({accion: accion === 'aplicar' && Object.keys(cambios).length ? 'aplicar' : 'omitir', cambios});
    m.remove();
  };
  const omitir = m.querySelector('#tr-omitir');
  omitir.textContent = info.omitir;
  omitir.onclick = () => responder('omitir');
  const aplicar = m.querySelector('#tr-aplicar');
  aplicar.textContent = info.aplicar;
  aplicar.onclick = () => responder('aplicar');
}
"""
