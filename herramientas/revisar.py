r"""Revisa el ultimo lote (la ultima corrida de main.py) y dice si todo quedo bien o que revisar.

1. Log de la corrida: personas, marcas escritas, errores y alertas (filtros que no cargaron, etc.).
2. Excel: como quedo cada persona (D-G formularios, H-M datos).
3. PDF unido de cada persona: que tenga todas las paginas de sus partes.
4. Analisis de coherencia (solo lectura) contra Kobo, el Excel y la hoja de Google.

Uso (con el bot cerrado y el Chrome de la hoja abierto):
    .venv\Scripts\python herramientas\revisar.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from tumaco import analisis, config, excel, sheets  # noqa: E402
from tumaco.browser import lanzar  # noqa: E402

PERSONA = re.compile(r"^\[(\d+)/(\d+)\] Usuario: (.*) \| USUARIO (\S+) \| CASA .* \(fila (\d+)\)")
ALERTAS = ("[ERROR]", "No encontre la caja", "no cargo sus columnas", "[!]", "NO QUEDO", "no quedo bien")
AVISOS = ("decidido en la ventana", "No encontrado", "Dudoso", "Revisar a mano", "Verificar")


def leer_log() -> tuple[Path, dict]:
    log = sorted((config.OUTPUT_DIR / "logs").glob("corrida_*.log"))[-1]
    personas, actual = {}, None
    for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if m := PERSONA.match(linea):
            actual = m.group(4)
            personas[actual] = {"nombre": m.group(3), "fila": int(m.group(5)), "alertas": [], "avisos": [],
                                "segundos": 0}
        elif actual:
            p = personas[actual]
            if any(a in linea for a in ALERTAS):
                p["alertas"].append(linea.strip())
            elif any(a in linea for a in AVISOS) and not linea.startswith(("   Casos por", "Con todos")):
                p["avisos"].append(linea.strip())
            if m := re.search(r"\| total (\d+)s", linea):
                p["segundos"] += int(m.group(1))
    return log, personas


def carpeta(usuario: excel.Usuario) -> Path | None:
    """Carpeta de la persona sin crearla ni renombrarla (solo para revisar)."""
    encontradas = sorted(config.CONTINGENCIAL_DIR.glob(f"{usuario.usuario}_*"))
    return encontradas[0] if encontradas else None


def revisar_pdf(usuario: excel.Usuario) -> str:
    c = carpeta(usuario)
    if not c:
        return "sin carpeta"
    unido = c / f"{c.name}.pdf"
    partes = [f for f in c.glob("*.pdf") if f != unido]
    if not unido.exists():
        return f"sin PDF unido ({len(partes)} parte(s))" if usuario.terminado() else f"en curso ({len(partes)} parte(s))"
    suma = sum(len(PdfReader(f).pages) for f in partes)
    paginas = len(PdfReader(unido).pages)
    estado = "OK" if paginas == suma else f"NO CUADRA (suma de partes {suma})"
    return f"{paginas} pag {estado}, {unido.stat().st_size / 1e6:.1f} MB, {len(partes)} parte(s)"


def main():
    log, lote = leer_log()
    usuarios = {u.usuario: u for u in excel.usuarios(excel.cargar_tabla())}
    print(f"Lote: {log.name} | {len(lote)} persona(s)\n")
    problemas = 0
    for num, info in lote.items():
        u = usuarios.get(num)
        if not u:
            continue
        marcas = " ".join(f"F{n}={u.marca(n) or '-'}"[:28] for n in sorted(excel.COLUMNA_FORMULARIO))
        print(f"{num} {u.nombre} (fila {u.fila}) | {info['segundos'] // 60}m{info['segundos'] % 60:02d}s")
        print(f"   Excel: {marcas} | H={u.propietario or '-'} I={u.documento or '-'} J={u.anexo or '-'} "
              f"K={u.hoja or '-'} L={u.nombre_final or '-'} M={u.casa_final or '-'}")
        print(f"   PDF unido: {revisar_pdf(u)}")
        for a in info["alertas"]:
            print(f"   [ALERTA] {a}")
        for a in info["avisos"]:
            print(f"   [aviso] {a}")
        problemas += len(info["alertas"]) + ("NO CUADRA" in revisar_pdf(u))

    print("\nAnalisis de coherencia (Kobo, Excel y hoja)...")
    with sync_playwright() as p:
        filas_hoja = sheets.leer_filas(sheets.Hoja(p).pestana())
        contexto = lanzar(p, headless=True)
        try:
            envios = analisis.descargar_envios(contexto.request)
        finally:
            contexto.close()
    resultado = analisis.analizar(excel.cargar_tabla(), envios, filas_hoja)
    del_lote = [x for x in resultado["personas"] if x["usuario"] in lote]
    if del_lote:
        print(analisis.resumen({"personas": del_lote}))
        problemas += sum(len(f["correcciones"]) + f["rehacer"] for x in del_lote for f in x["formularios"])
    else:
        print("   Sin diferencias para las personas de este lote.")
    print(f"\n{'TODO BIEN en este lote.' if not problemas else f'REVISAR: {problemas} punto(s) arriba.'}")


if __name__ == "__main__":
    main()
