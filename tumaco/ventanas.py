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
