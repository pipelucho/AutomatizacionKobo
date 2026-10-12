r"""Aplica las correcciones de herramientas\analizar.py (salida\analisis_correcciones.json),
preguntando en una ventana cada cambio antes de hacerlo.

Para cada persona:
1. Formularios a rehacer (el bot proceso el registro de otra persona): confirmas en una ventana y se
   borra su marca en el Excel y su PDF, para que main.py los haga de nuevo con la busqueda segura.
2. Formularios a parchar: se abren directo (por su _id en Kobo, sin buscarlos en la tabla) y sobre el
   formulario aparece la ventana con cada cambio: lo marcas o no, y puedes editar el valor. Solo se
   cambian esos campos (no se vuelve a firmar, ni se tocan cedulas ni documentos), se genera su PDF y se
   envia. Si no marcas nada, el formulario no se toca.
3. Hoja de Google y Excel (nombre final L, casa final M): otra ventana con las celdas.
Al final se rehace el PDF unido de quien cambio y los avisos quedan en CASOS.xlsx.

Uso (con el bot cerrado, el Excel cerrado y el Chrome de la hoja abierto):
    .venv\Scripts\python herramientas\corregir.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tumaco import analisis, casos, config, excel, pdf, sheets, ventanas  # noqa: E402
from tumaco.browser import abrir_navegador  # noqa: E402
from tumaco.humano import pegar  # noqa: E402
from tumaco.kobo import Kobo  # noqa: E402

NOMBRES_CAMPO = {"nombre": "Nombre", "nombre_firma": "Nombre junto a la firma", "direccion": "Dirección"}


def tipo_aviso(texto: str) -> str:
    if "OTRA persona" in texto or "ningun registro" in texto:
        return "Registro ajeno"
    if "posible duplicado" in texto or "nunca fue corregido" in texto:
        return "Registro duplicado"
    return "Verificar casa" if " casa:" in texto else "Verificar nombre"


def contexto(u: excel.Usuario, p: dict, numero: int | None = None) -> list[str]:
    lineas = [f"Excel: {u.nombre} | usuario {u.usuario} | casa {u.casa or '-'} | documento {u.documento or '-'}"]
    return lineas + [a for a in p["avisos"] if numero is None or a.startswith((f"F{numero} ", f"F{numero}:"))]


def rehacer(kobo: Kobo, u: excel.Usuario, p: dict, carpeta: Path) -> bool:
    formularios = [f["formulario"] for f in p["formularios"] if f["rehacer"]] + p.get("sin_registro", [])
    if not formularios:
        return False
    cambios = [{"id": str(n), "campo": f"Formulario {n}", "actual": f"marcado '{u.marca(n)}' en el Excel",
                "nuevo": "Rehacer: borrar la marca y su PDF", "editable": False,
                "detalle": "El bot lo hara de nuevo con la busqueda segura (si no hay registro propio: 'No encontrado')"}
               for n in formularios]
    elegidos = ventanas.revisar_cambios(kobo.page, f"{u.nombre} (usuario {u.usuario}): formularios a rehacer",
                                        contexto(u, p), cambios, aplicar="Rehacer los marcados")
    for n in map(int, elegidos or {}):
        excel.marcar(u.fila, "", excel.COLUMNA_FORMULARIO[n])
        for viejo in carpeta.glob(f"{n}. *.pdf"):
            viejo.unlink()
            print(f"   Formulario {n}: PDF de otro registro borrado ({viejo.name})")
        print(f"   Formulario {n}: marca borrada en el Excel; el bot lo rehace en la proxima corrida")
    return bool(elegidos)


def parchar(kobo: Kobo, u: excel.Usuario, p: dict, form: dict, carpeta: Path) -> bool | None:
    """Abre el formulario por su _id y muestra la ventana; aplica solo lo marcado, genera el PDF y envia.
    True = enviado, False = fallo, None = no se cambio nada."""
    n = form["formulario"]
    resp = kobo.page.request.get(f"{config.KOBO_URL}/api/v2/assets/{form['uid']}/data/{form['_id']}/enketo/edit/",
                                 params={"return_url": "false"})
    if not resp.ok:
        print(f"   [!] Kobo no dio el enlace de edicion (HTTP {resp.status})")
        return False
    edicion = kobo.page.context.new_page()
    try:
        edicion.goto(resp.json()["url"])
        edicion.locator("form.or").first.wait_for(timeout=90_000)
        edicion.wait_for_timeout(1000)
        cambios = [{"id": xpath, "campo": NOMBRES_CAMPO.get(c["campo"], c["campo"]), "actual": c["actual"],
                    "nuevo": c["nuevo"],
                    "detalle": (f"Antes de que el bot lo cambiara decia: '{c['original']}'"
                                if form["con_log"] and c["original"] != c["actual"] else "")}
                   for xpath, c in form["correcciones"].items()]
        elegidos = ventanas.revisar_cambios(edicion, f"Formulario {n} de {u.nombre} (usuario {u.usuario})",
                                            contexto(u, p, n), cambios, aplicar="Aplicar y enviar")
        if not elegidos:
            print("   No se cambio nada (decidido en la ventana)")
            return None
        for xpath, valor in elegidos.items():
            campo = edicion.locator(f'[name="/{form["uid"]}/{xpath}"]').first
            pegar(campo, valor)
            campo.dispatch_event("change")
            if campo.input_value() != valor:
                print(f"   [!] {xpath} no quedo: '{campo.input_value()}'")
                return False
            print(f"   * {NOMBRES_CAMPO.get(form['correcciones'][xpath]['campo'], xpath)}: "
                  f"'{form['correcciones'][xpath]['actual']}' -> '{valor}'")
        pdf.guardar_pdf(edicion, carpeta)
        return kobo.enviar_edicion(edicion)
    finally:
        if not edicion.is_closed():
            edicion.close()


def hoja_y_excel(kobo: Kobo, hoja: sheets.Hoja, u: excel.Usuario, p: dict) -> list[str]:
    cambios = [{"id": f"hoja:{celda}", "campo": f"Hoja {celda}", "actual": c["actual"], "nuevo": c["nuevo"],
                "detalle": {"F": "Usuario final", "H": "Direccion / barrio"}.get(celda[0], "")}
               for celda, c in p["hoja"].items()]
    if p["nombre_final"] and p["nombre_final"] != u.nombre_final:
        nueva = pdf.nombre_valido(f"{u.usuario}_{p['nombre_final'].upper()}")
        cambios.append({"id": "excel:L", "campo": "Excel L (nombre final)", "actual": u.nombre_final,
                        "nuevo": p["nombre_final"],
                        "detalle": f"Nombre de quien atendio. Tambien renombra la carpeta y el PDF unido a '{nueva}'"})
    if p["casa_final"] and p["casa_final"] != u.casa_final:
        cambios.append({"id": "excel:M", "campo": "Excel M (casa final)", "actual": u.casa_final,
                        "nuevo": p["casa_final"], "detalle": "Casa que quedo en el formulario 1"})
    if not cambios:
        return []
    elegidos = ventanas.revisar_cambios(kobo.page, f"{u.nombre} (usuario {u.usuario}): hoja de Google y Excel",
                                        contexto(u, p), cambios) or {}
    hechos = []
    celdas = {k.split(":")[1]: v for k, v in elegidos.items() if k.startswith("hoja:")}
    if celdas:
        pestana = hoja.pestana()
        for celda, valor in celdas.items():
            sheets.escribir_celda(pestana, celda, valor)
        filas = sheets.leer_filas(pestana)
        for celda, valor in celdas.items():
            quedo = sheets._celda(filas, int(celda[1:]), celda[0])
            print(f"   Hoja {celda} = '{valor}'" + ("" if quedo == valor else f"  [!] NO QUEDO: '{quedo}'"))
            if quedo == valor:
                hechos.append(f"hoja {celda}")
        kobo.page.bring_to_front()
    for clave, columna, campo in (("excel:L", excel.COL_NOMBRE_FINAL, "nombre_final"),
                                  ("excel:M", excel.COL_CASA_FINAL, "casa_final")):
        if clave in elegidos:
            excel.marcar(u.fila, elegidos[clave], columna)
            setattr(u, campo, elegidos[clave])
            print(f"   Excel {clave[-1]} = '{elegidos[clave]}'")
            hechos.append(f"excel {clave[-1]}")
    return hechos


def main():
    plan = json.loads(analisis.ANALISIS_PATH.read_text(encoding="utf-8"))
    personas = plan["personas"]
    print(analisis.resumen(plan))
    print("\nCada cambio se confirma en una ventana del navegador.")

    usuarios = {u.usuario: u for u in excel.usuarios(excel.cargar_tabla())}
    hechos, fallas, omitidos = [], [], []
    with abrir_navegador() as (_, page, playwright):
        kobo = Kobo(page)
        kobo.iniciar_sesion()
        hoja = sheets.Hoja(playwright)
        for p in personas:
            u = usuarios[p["usuario"]]
            carpeta = pdf.carpeta_persona(u)
            print(f"\n=== {u.usuario} {u.nombre} (fila {u.fila}) ===")
            cambio_pdf = rehacer(kobo, u, p, carpeta)
            for f in p["formularios"]:
                if f["rehacer"] or not f["correcciones"]:
                    continue
                print(f"Formulario {f['formulario']} (_id {f['_id']}):")
                resultado = parchar(kobo, u, p, f, carpeta)
                destino = {True: hechos, False: fallas, None: omitidos}[resultado]
                destino.append(f"{u.usuario} F{f['formulario']}")
                # Aunque el envio falle, su PDF ya se regenero: el unido debe coincidir con el
                cambio_pdf = cambio_pdf or resultado is not None
            hechos += [f"{u.usuario} {h}" for h in hoja_y_excel(kobo, hoja, u, p)]
            nueva = pdf.carpeta_persona(u)  # si se acepto el nombre final, renombra la carpeta
            if cambio_pdf or nueva != carpeta:
                pdf.unir_pdfs(nueva)
            for texto in p["avisos"]:
                numero = int(texto[1]) if texto[:1] == "F" and texto[1:2].isdigit() else 1
                casos.anotar_aviso(u, numero, tipo_aviso(texto), texto.split(":", 1)[1].strip())

        excel.guardar_pendientes(esperar=True)
        filas_casos = casos.actualizar(excel.cargar_tabla())
        print(f"\nAplicados: {len(hechos)} | No cambiados (decidido en la ventana): {len(omitidos)} | "
              f"Con problema: {len(fallas)} {fallas or ''}")
        if filas_casos:
            print(casos.resumen(filas_casos))
        print("Los formularios a rehacer quedan para la proxima corrida de main.py.")
        input("\nPresiona Enter para cerrar el navegador...")


if __name__ == "__main__":
    main()
