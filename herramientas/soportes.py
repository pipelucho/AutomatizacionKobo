r"""Recorre a las personas ya procesadas con documento anexo y corrige el texto de soportes de la hoja.

Para cada persona con documento anexo conservado (columna J del Excel = Si) y su fila ya llena en la
hoja (K = Si), muestra el documento del formulario 1 ("Soporte de propiedad sobre el inmueble", traido
de la API de Kobo) y un campo con lo que dice hoy la columna J de la hoja. Al guardar:
- se cambia SOLO esa celda J de la hoja de Google (y se verifica);
- se guarda el texto en la columna N del Excel, para que el bot use el mismo si vuelve a llenar la hoja.
En Kobo no se cambia nada.

Uso (con el bot cerrado, el Excel cerrado y el Chrome de la hoja abierto):
    .venv\Scripts\python herramientas\soportes.py
"""
import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from tumaco import analisis, config, excel, reglas, sheets, ventanas  # noqa: E402
from tumaco.browser import abrir_navegador  # noqa: E402
from tumaco.kobo import Kobo  # noqa: E402

CAMPO_SOPORTE = "group_re9nr91/soporte_propiedad_inmueble"  # formulario 1: Soporte de propiedad sobre el inmueble


def envios_formulario1(request) -> tuple[str, dict, list[dict]]:
    """(uid, campos, envios con sus adjuntos) del formulario 1."""
    activos = request.get(f"{config.KOBO_URL}/api/v2/assets/", params={"format": "json", "q": "asset_type:survey",
                                                                     "limit": "100"}).json()["results"]
    uid = next(a["uid"] for a in activos if analisis.norm(a["name"]).startswith(analisis.norm(config.FORMULARIOS[0])[:20]))
    campos = analisis.CAMPOS[1]
    pedir = ["_id", "_attachments", CAMPO_SOPORTE, *campos.values()]
    envios = request.get(f"{config.KOBO_URL}/api/v2/assets/{uid}/data/",
                         params={"format": "json", "limit": "30000", "fields": json.dumps(pedir)}).json()["results"]
    return uid, campos, envios


def imagen_documento(request, envio: dict) -> tuple[str | None, str]:
    """(imagen como data URL reducida, nombre del archivo) del soporte de propiedad del envio."""
    archivo = str(envio.get(CAMPO_SOPORTE, "") or "")
    if not archivo:
        return None, ""
    adjunto = next((a for a in envio.get("_attachments", [])
                    if str(a.get("filename", "")).endswith(archivo) and str(a.get("is_deleted")) != "True"), None)
    if not adjunto:
        return None, archivo
    resp = request.get(adjunto.get("download_large_url") or adjunto["download_url"])
    if not resp.ok or not str(adjunto.get("mimetype", "")).startswith("image"):
        return None, archivo
    img = Image.open(io.BytesIO(resp.body())).convert("RGB")
    img.thumbnail((1400, 1400))
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(salida.getvalue()).decode(), archivo


def main():
    tabla = excel.cargar_tabla()
    personas = [u for u in excel.usuarios(tabla) if u.anexo.lower() == "si" and u.hoja]
    print(f"{len(personas)} persona(s) procesadas con documento anexo y su fila en la hoja.")
    if not personas:
        return
    cambios = {}
    with abrir_navegador() as (_, page, playwright):
        kobo = Kobo(page)
        kobo.iniciar_sesion()
        pestana = sheets.Hoja(playwright).pestana()
        filas = sheets.leer_filas(pestana)
        uid, campos, envios = envios_formulario1(page.request)
        page.goto("about:blank")  # pagina limpia para mostrar las ventanas
        for n, u in enumerate(personas, start=1):
            fila_hoja = sheets.buscar_fila(filas, u.usuario)
            if not fila_hoja:
                print(f"{u.usuario} {u.nombre}: no esta en la hoja; se salta")
                continue
            actual = sheets._celda(filas, fila_hoja, sheets.COL_SOPORTE)
            envio, _, _ = analisis.buscar_envio(envios, campos, u)
            imagen, archivo = imagen_documento(page.request, envio) if envio else (None, "")
            accion, texto = ventanas.escribir_texto(
                page, f"[{n}/{len(personas)}] {u.usuario} {u.nombre_final or u.nombre}",
                [f"Documento anexo del formulario 1: {archivo or 'no se encontro en Kobo'}",
                 f"Hoy en la hoja (J{fila_hoja}): {actual or '(vacio)'}",
                 "Escribe los soportes que van en la columna J. Solo cambia la hoja (y la columna N del Excel)."],
                imagen, "Soportes (columna J de la hoja):", actual or reglas.SOPORTE_CON_ANEXO)
            if accion == "terminar":
                print("Recorrido terminado por ti.")
                break
            texto = reglas.limpio(texto)
            if accion == "igual" or not texto or texto == reglas.limpio(actual):
                print(f"{u.usuario} {u.nombre}: se deja igual ({actual})")
                continue
            sheets.escribir_celda(pestana, f"{sheets.COL_SOPORTE}{fila_hoja}", texto)
            excel.marcar(u.fila, texto, excel.COL_SOPORTE)
            cambios[f"{sheets.COL_SOPORTE}{fila_hoja}"] = (u, actual, texto)
            print(f"{u.usuario} {u.nombre}: J{fila_hoja} '{actual}' -> '{texto}'")
            page.bring_to_front()

        if cambios:
            print("\nVerificando la hoja...")
            filas = sheets.leer_filas(pestana)
            for celda, (u, antes, texto) in cambios.items():
                quedo = sheets._celda(filas, int(celda[1:]), celda[0])
                print(f"   {celda} {u.usuario}: {'OK' if quedo == texto else 'NO QUEDO: ' + quedo}")
        excel.guardar_pendientes(esperar=True)
        print(f"\nCeldas cambiadas: {len(cambios)}")
        input("\nPresiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
