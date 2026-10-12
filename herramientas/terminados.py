r"""Mueve a CONTINGENCIAL\TERMINADOS\LISTOS POR CARGAR las carpetas de las personas terminadas sin problemas.

Una persona queda lista si:
- todos sus formularios quedaron enviados (el 4 puede ser 'No encontrado': hay personas sin el) y
  ninguno dice 'Revisar a mano';
- su fila de la hoja de Google quedo llena (columna K = Si);
- su PDF unido existe y tiene todas las paginas de sus partes;
- no tiene casos pendientes en CASOS.xlsx (salvo 'Sin formulario 4'), ni correcciones o avisos en el
  ultimo analisis (salida\analisis_correcciones.json, lo genera herramientas\revisar.py o analizar.py);
- su nombre no tiene letras dañadas (ej. 'QUIÃ‘ONES') ni parece cortado (el Excel corta a 31 letras).

Si despues hay que cambiar algo de una persona terminada, el bot y corregir.py devuelven su carpeta a
CONTINGENCIAL solos. Se puede correr de nuevo cuando se resuelvan mas casos.

Uso:
    .venv\Scripts\python herramientas\terminados.py            (solo muestra quien esta listo)
    .venv\Scripts\python herramientas\terminados.py --mover    (y mueve sus carpetas)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from revisar import carpeta, revisar_pdf  # noqa: E402
from tumaco import analisis, casos, config, excel  # noqa: E402

LARGO_CORTADO = 31  # el Excel trae los nombres cortados a 31 letras
CASOS_INFORMATIVOS = {"Sin formulario 4"}


def problemas(u: excel.Usuario, analizadas: dict, pendientes: dict) -> list[str]:
    motivos = []
    if not u.terminado():
        motivos.append("formularios sin terminar ("
                       + ", ".join(f"F{n}: {u.marca(n) or '-'}"[:45] for n in sorted(excel.COLUMNA_FORMULARIO)) + ")")
    if any(u.marca(n).lower().startswith(excel.MARCA_A_MANO.lower()) for n in excel.COLUMNA_FORMULARIO):
        motivos.append("un formulario quedo para revisar a mano")
    if u.hoja.lower() != "si":
        motivos.append("su fila de la hoja de Google no esta llena")
    estado_pdf = revisar_pdf(u)
    if " OK" not in estado_pdf:
        motivos.append(f"PDF unido: {estado_pdf}")
    if a := analizadas.get(u.usuario):
        if any(f["correcciones"] or f["rehacer"] for f in a["formularios"]) or a["hoja"] or a["sin_registro"]:
            motivos.append("el analisis tiene correcciones pendientes")
        motivos += [f"aviso del analisis: {aviso}" for aviso in a["avisos"]]
    motivos += [f"caso pendiente: {c}" for c in pendientes.get(u.usuario, [])]
    nombre = u.nombre_final or u.nombre
    if "Ã" in nombre or "Â" in nombre:
        motivos.append(f"nombre con letras dañadas: {nombre}")
    elif not u.nombre_final and len(u.nombre) >= LARGO_CORTADO:
        motivos.append(f"nombre posiblemente cortado en el Excel: {u.nombre}")
    return motivos


def main():
    mover = "--mover" in sys.argv
    if analisis.ANALISIS_PATH.exists():
        analizadas = {p["usuario"]: p for p in json.loads(analisis.ANALISIS_PATH.read_text(encoding="utf-8"))["personas"]}
        fecha = datetime.fromtimestamp(analisis.ANALISIS_PATH.stat().st_mtime)
        print(f"Analisis usado: {analisis.ANALISIS_PATH.name} del {fecha:%Y-%m-%d %H:%M}")
    else:
        analizadas = {}
        print("[!] No hay analisis: corre antes herramientas\\revisar.py o analizar.py")
    pendientes = {}
    for c in casos._leer():
        if c.get("Estado") == casos.PENDIENTE and c.get("Tipo") not in CASOS_INFORMATIVOS:
            pendientes.setdefault(str(c.get("Usuario", "")).strip(), []).append(
                f"{c.get('Tipo')} ({str(c.get('Detalle', ''))[:80]})")

    listos, con_problemas = [], []
    for u in excel.usuarios(excel.cargar_tabla()):
        c = carpeta(u)
        motivos = problemas(u, analizadas, pendientes)
        (con_problemas if motivos else listos).append((u, c, motivos))

    config.LISTOS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nTerminadas sin problemas: {len(listos)}")
    movidas = 0
    for u, c, _ in listos:
        sin_f4 = " (sin formulario 4)" if u.marca(4).lower() == excel.MARCA_NO_ENCONTRADO.lower() else ""
        if c.parent == config.POR_CORREGIR_DIR:
            print(f"   {c.name}{sin_f4}: esta en POR CORREGIR; se deja ahi hasta que la saques tu")
        elif c.parent == config.TERMINADOS_DIR or c.parent.parent == config.TERMINADOS_DIR:
            print(f"   {c.name}{sin_f4}: ya estaba en TERMINADOS ({c.parent.name})")
        elif mover:
            c.rename(config.LISTOS_DIR / c.name)
            movidas += 1
            print(f"   {c.name}{sin_f4}: movida a LISTOS POR CARGAR")
        else:
            print(f"   {c.name}{sin_f4}")

    print(f"\nCon algo pendiente: {len(con_problemas)}")
    for u, c, motivos in con_problemas:
        donde = "" if c else " (sin carpeta)"
        if c and (c.parent == config.TERMINADOS_DIR or c.parent.parent == config.TERMINADOS_DIR):
            donde = f" (esta en {c.parent.name}: se deja ahi)"
        print(f"   {u.usuario} {u.nombre_final or u.nombre}{donde}")
        for m in motivos:
            print(f"      - {m[:160]}")

    if mover:
        print(f"\nCarpetas movidas a LISTOS POR CARGAR: {movidas}")
    else:
        print("\nNo se movio nada. Para moverlas: .venv\\Scripts\\python herramientas\\terminados.py --mover")


if __name__ == "__main__":
    main()
