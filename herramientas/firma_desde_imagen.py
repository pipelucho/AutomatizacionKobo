"""Convierte la imagen de una firma en trazos (lineas que dibuja el mouse) y los guarda en JSON.

Uso:
    .venv\\Scripts\\python herramientas\\firma_desde_imagen.py firmas\\contratista_origen.png firmas\\contratista.json
    (opcional) --recorte x1,y1,x2,y2   zona de la imagen donde esta el lienzo
    (opcional) --min-trazo 1           conservar puntos sueltos (por defecto se descartan trazos de menos de 6 px)

Requiere: pip install -r requirements-herramientas.txt
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

VECINOS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def esqueleto(ruta: Path, recorte) -> np.ndarray:
    img = Image.open(ruta).convert("L")
    if recorte:
        img = img.crop(recorte)
    tinta = np.array(img) < 110
    return skeletonize(tinta)


def trazar(esq: np.ndarray, minimo: int = 6) -> list[list[tuple[int, int]]]:
    """Recorre el esqueleto de un pixel de ancho y lo parte en trazos continuos."""
    pixeles = {(int(y), int(x)) for y, x in zip(*np.nonzero(esq))}

    def vecinos(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in VECINOS if (p[0] + dy, p[1] + dx) in pixeles]

    visitados = set()
    trazos = []
    # Primero desde las puntas (grado 1), luego lo que quede (curvas cerradas)
    puntas = [p for p in pixeles if len(vecinos(p)) == 1]
    for inicio in puntas + sorted(pixeles):
        if inicio in visitados:
            continue
        trazo = [inicio]
        visitados.add(inicio)
        actual = inicio
        while True:
            libres = [v for v in vecinos(actual) if v not in visitados]
            if not libres:
                break
            # preferir vecinos rectos para un recorrido suave
            libres.sort(key=lambda v: abs(v[0] - actual[0]) + abs(v[1] - actual[1]))
            actual = libres[0]
            visitados.add(actual)
            trazo.append(actual)
        if len(trazo) >= minimo:
            trazos.append([(x, y) for y, x in trazo])
    return trazos


def suavizar(puntos, ventana=5):
    """Promedio movil: quita el escalonado de los pixeles del esqueleto (conserva los extremos)."""
    if len(puntos) < ventana:
        return puntos
    arr = np.array(puntos, float)
    m = ventana // 2
    medio = [tuple(arr[max(0, i - m): i + m + 1].mean(axis=0)) for i in range(1, len(arr) - 1)]
    return [tuple(arr[0]), *medio, tuple(arr[-1])]


def simplificar(puntos, epsilon=1.2):
    """Ramer-Douglas-Peucker: menos puntos, misma forma."""
    if len(puntos) < 3:
        return puntos
    a, b = np.array(puntos[0], float), np.array(puntos[-1], float)
    ab = b - a
    largo = np.hypot(*ab) or 1.0
    dist = [abs(ab[0] * (a[1] - p[1]) - ab[1] * (a[0] - p[0])) / largo for p in puntos[1:-1]]
    i = int(np.argmax(dist)) + 1
    if dist[i - 1] > epsilon:
        return simplificar(puntos[: i + 1], epsilon)[:-1] + simplificar(puntos[i:], epsilon)
    return [puntos[0], puntos[-1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagen")
    ap.add_argument("salida")
    ap.add_argument("--recorte", help="x1,y1,x2,y2")
    ap.add_argument("--min-trazo", type=int, default=6,
                    help="pixeles minimos de un trazo; bajarlo (ej. 1) conserva puntos como el de S.M")
    ap.add_argument("--detalle", type=float, default=0.6,
                    help="tolerancia en pixeles al simplificar; menor = curvas mas fieles y mas puntos")
    args = ap.parse_args()

    recorte = tuple(int(v) for v in args.recorte.split(",")) if args.recorte else None
    trazos = [simplificar(suavizar(t), args.detalle)
              for t in trazar(esqueleto(Path(args.imagen), recorte), args.min_trazo)]
    xs = [x for t in trazos for x, _ in t]
    ys = [y for t in trazos for _, y in t]
    x0, y0, ancho, alto = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    # Coordenadas normalizadas 0..1 dentro del recuadro de la firma
    datos = {
        "ancho": ancho,
        "alto": alto,
        "trazos": [[[round((x - x0) / ancho, 5), round((y - y0) / alto, 5)] for x, y in t] for t in trazos],
    }
    Path(args.salida).write_text(json.dumps(datos), encoding="utf-8")
    print(f"{len(trazos)} trazos, {sum(len(t) for t in trazos)} puntos -> {args.salida}")


if __name__ == "__main__":
    main()
