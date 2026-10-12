"""Recorta una foto de cedula al borde del documento y la endereza (horizontal y derecha)."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Una cedula (tamaño tarjeta ID-1: 85,6 x 54 mm) es 1,585 veces mas ancha que alta
PROPORCION = 85.6 / 54
LADO_DETECCION = 1000  # la deteccion se hace sobre una copia reducida (mas rapido y estable)
ANCHO_MAXIMO = 1800  # ancho de la imagen ajustada que se sube a Kobo
CONFIANZA_MINIMA = 0.75  # por debajo, lo encontrado probablemente no es la tarjeta: se deja la foto original


@dataclass
class Recorte:
    imagen: np.ndarray  # documento recortado, enderezado y horizontal (BGR)
    esquinas: np.ndarray  # 4 esquinas del documento en la foto original
    confianza: float  # 0 a 1: que tanto parece una tarjeta el contorno encontrado
    metodo: str


def recortar(foto: np.ndarray) -> Recorte | None:
    """Busca la tarjeta en la foto y la devuelve recortada al borde y horizontal.

    Prueba varias formas de separar la tarjeta del fondo (color, bordes) y se queda con el
    contorno que mas se parece a un rectangulo con la proporcion de una cedula.
    """
    escala = LADO_DETECCION / max(foto.shape[:2])
    peque = cv2.resize(foto, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else foto.copy()
    escala = min(escala, 1.0)

    mejor = None
    for metodo, mascara in _mascaras(peque):
        for contorno in _contornos(mascara):
            puntos = _evaluar(contorno, peque.shape)
            if puntos and (mejor is None or puntos[0] > mejor[0]):
                mejor = (puntos[0], puntos[1], metodo)
    if not mejor:
        return None
    confianza, esquinas, metodo = mejor
    esquinas = esquinas / escala
    return Recorte(imagen=_enderezar(foto, esquinas), esquinas=esquinas, confianza=confianza, metodo=metodo)


def _mascaras(img: np.ndarray):
    """Distintas separaciones tarjeta/fondo; cada una funciona mejor con cierto tipo de foto."""
    suave = cv2.GaussianBlur(img, (5, 5), 0)
    lab = cv2.cvtColor(suave, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)
    nucleo = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))

    def limpiar(m):
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, nucleo, iterations=2)
        return cv2.morphologyEx(m, cv2.MORPH_OPEN, nucleo, iterations=1)

    # 1. Color: la cedula amarilla es mas "amarilla" (canal b de LAB) que el fondo
    _, amarillo = cv2.threshold(lab[:, :, 2], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "color", limpiar(amarillo)
    # 2. Saturacion: tarjeta con color sobre fondo gris/blanco (o al reves)
    _, saturada = cv2.threshold(hsv[:, :, 1], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "saturacion", limpiar(saturada)
    yield "saturacion-inv", limpiar(255 - saturada)
    # 3. Brillo: tarjeta clara sobre fondo oscuro (o al reves)
    _, clara = cv2.threshold(lab[:, :, 0], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "brillo", limpiar(clara)
    yield "brillo-inv", limpiar(255 - clara)
    # 4. Bordes: el contorno de la tarjeta como linea
    gris = cv2.cvtColor(suave, cv2.COLOR_BGR2GRAY)
    bordes = cv2.Canny(gris, 40, 120)
    bordes = cv2.dilate(bordes, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
    yield "bordes", bordes


def _contornos(mascara: np.ndarray):
    contornos, _ = cv2.findContours(mascara, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return sorted(contornos, key=cv2.contourArea, reverse=True)[:8]


def _evaluar(contorno, forma) -> tuple[float, np.ndarray] | None:
    """Puntaje (0 a 1) de que tanto parece una cedula y sus 4 esquinas, o None si no lo parece."""
    area_img = forma[0] * forma[1]
    area = cv2.contourArea(contorno)
    if not 0.05 * area_img < area < 0.97 * area_img:
        return None
    rect = cv2.minAreaRect(contorno)
    (w, h) = rect[1]
    if min(w, h) == 0:
        return None
    proporcion = max(w, h) / min(w, h)
    rectangular = area / (w * h)  # 1 = rectangulo perfecto
    if rectangular < 0.8 or not 1.3 < proporcion < 1.9:
        return None

    casco = cv2.convexHull(contorno)
    esquinas = None
    perimetro = cv2.arcLength(casco, True)
    for eps in (0.01, 0.02, 0.03, 0.04, 0.05):
        aprox = cv2.approxPolyDP(casco, eps * perimetro, True)
        if len(aprox) == 4:
            esquinas = aprox.reshape(4, 2).astype(np.float32)
            break
    if esquinas is None or cv2.contourArea(esquinas) < 0.85 * w * h:
        esquinas = cv2.boxPoints(rect).astype(np.float32)  # sin 4 esquinas claras: rectangulo minimo

    parecido_proporcion = max(0.0, 1 - abs(proporcion - PROPORCION) / 0.4)
    tamano = min(1.0, area / (0.15 * area_img))  # las tarjetas muy pequeñas suelen ser ruido
    return (0.5 * rectangular + 0.35 * parecido_proporcion + 0.15 * tamano), _ordenar(esquinas)


def _ordenar(p: np.ndarray) -> np.ndarray:
    """Esquinas en orden: arriba-izq, arriba-der, abajo-der, abajo-izq."""
    centro = p.mean(axis=0)
    angulos = np.arctan2(p[:, 1] - centro[1], p[:, 0] - centro[0])
    p = p[np.argsort(angulos)]  # orden horario empezando por arriba-izq (aprox)
    inicio = np.argmin(p.sum(axis=1))
    return np.roll(p, -inicio, axis=0)


def _enderezar(foto: np.ndarray, esquinas: np.ndarray) -> np.ndarray:
    """Corrige la perspectiva y deja la tarjeta horizontal (lado largo abajo y arriba)."""
    tl, tr, br, bl = esquinas
    ancho = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    alto = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    vertical = alto > ancho
    if vertical:
        ancho, alto = alto, ancho
    # Tamaño final con la proporcion exacta de la cedula, sin perder resolucion
    ancho = int(round(ancho))
    alto = int(round(ancho / PROPORCION))
    if vertical:  # el lado largo esta vertical en la foto: se recorre empezando por abajo-izq
        origen = np.array([bl, tl, tr, br], dtype=np.float32)
    else:
        origen = np.array([tl, tr, br, bl], dtype=np.float32)
    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(origen, destino)
    return cv2.warpPerspective(foto, matriz, (ancho, alto), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


# ---------- Orientacion (derecha o de cabeza) ----------
#
# Despues de recortar, la tarjeta queda horizontal pero puede estar de cabeza. Se combinan pistas;
# cada una da un valor de -1 (esta de cabeza) a 1 (esta derecha), 0 si no aporta:
#   - rostro (cara): la foto de la persona solo se detecta como rostro cuando esta derecha.
#   - codigo de barras (reverso de la cedula amarilla): va en la mitad de abajo.
#   - plantillas: parecido con cedulas derechas de cada modelo (amarilla y digital) en plantillas_cedula/.

PLANTILLAS_DIR = Path(__file__).parent / "plantillas_cedula"
SUMA_SEGURA = 0.8  # suma minima de las pistas para decidir sin dudar
CONTRADICCION = 0.5  # si una pista dice lo contrario con esta fuerza, hay duda

_DETECTORES_ROSTRO = None
_PLANTILLAS = None


def orientar(img: np.ndarray, lado: str) -> tuple[np.ndarray, bool]:
    """Deja la tarjeta derecha (no de cabeza). Devuelve (imagen, seguro).

    `seguro` es False cuando las pistas no son claras o se contradicen.
    """
    pistas = _pistas(img, lado)
    girada = cv2.rotate(img, cv2.ROTATE_180)
    suma = sum(pistas.values())
    contradice = any(abs(v) >= CONTRADICCION and np.sign(v) != np.sign(suma) for v in pistas.values())
    seguro = abs(suma) >= SUMA_SEGURA and not contradice
    return (img if suma >= 0 else girada), seguro


def pistas_orientacion(img: np.ndarray, lado: str) -> dict:
    """Valores de cada pista (para revisar casos dudosos)."""
    return {k: round(float(v), 2) for k, v in _pistas(img, lado).items()}


def _pistas(img: np.ndarray, lado: str) -> dict:
    girada = cv2.rotate(img, cv2.ROTATE_180)
    pistas = {"plantilla": _pista_plantilla(img, girada, lado)}
    if lado == "cara":
        pistas["rostro"] = (_rostros(img) - _rostros(girada)) / 6
    elif modelo(img, lado) == "amarilla":
        # El codigo de barras abajo solo existe en el reverso de la cedula amarilla; en la digital
        # (QR y lineas ICCOL<<<) esa pista confunde y hacia dudar con fotos derechas
        pistas["barras"] = float(np.clip((_barras_abajo(img) - 0.5) / 0.12, -1, 1))
    return pistas


def modelo(img: np.ndarray, lado: str) -> str:
    """'amarilla' o 'digital': la plantilla que mas se parece (derecha o de cabeza)."""
    _cargar_plantillas()
    a, b = _huella(img), _huella(cv2.rotate(img, cv2.ROTATE_180))
    parecido = {nombre.split("_")[0]: max(float((a * h).mean()), float((b * h).mean()))
                for nombre, h in _PLANTILLAS.items() if nombre.endswith(lado)}
    return max(parecido, key=parecido.get) if parecido else "amarilla"


def _rostros(img: np.ndarray) -> int:
    """Cuantos detectores (2 modelos x 3 ajustes de luz) ven un rostro derecho del tamaño de la foto."""
    global _DETECTORES_ROSTRO
    if _DETECTORES_ROSTRO is None:
        _DETECTORES_ROSTRO = [cv2.CascadeClassifier(cv2.data.haarcascades + n)
                              for n in ("haarcascade_frontalface_alt.xml", "haarcascade_frontalface_alt2.xml")]
    alto = 500
    gris = cv2.cvtColor(cv2.resize(img, (int(alto * img.shape[1] / img.shape[0]), alto)), cv2.COLOR_BGR2GRAY)
    variantes = (gris, cv2.equalizeHist(gris), cv2.createCLAHE(2.0, (8, 8)).apply(gris))
    minimo = int(0.16 * alto)  # la foto ocupa buena parte del alto; los rostros pequeños son falsos
    return sum(1 for detector in _DETECTORES_ROSTRO for g in variantes
               if len(detector.detectMultiScale(g, 1.05, 3, minSize=(minimo, minimo))))


def _barras_abajo(img: np.ndarray) -> float:
    """Que tanto el codigo de barras (rayas verticales densas) esta en la mitad de abajo (0 a 1)."""
    gris = cv2.cvtColor(cv2.resize(img, (640, int(640 * img.shape[0] / img.shape[1]))), cv2.COLOR_BGR2GRAY)
    gx = np.abs(cv2.Sobel(gris, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(gris, cv2.CV_32F, 0, 1, ksize=3))
    rayas = cv2.blur(np.clip(gx - gy, 0, None), (25, 25))
    mitad = rayas.shape[0] // 2
    arriba, abajo = float(rayas[:mitad].sum()), float(rayas[mitad:].sum())
    return abajo / (arriba + abajo + 1e-6)


def _huella(img: np.ndarray) -> np.ndarray:
    """Version reducida y normalizada de la tarjeta para comparar su distribucion (texto, foto, barras)."""
    gris = cv2.cvtColor(cv2.resize(img, (160, 101), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(cv2.createCLAHE(2.0, (4, 4)).apply(gris), (5, 5), 0).astype(np.float32)
    return (gris - gris.mean()) / (gris.std() + 1e-6)


def _pista_plantilla(img: np.ndarray, girada: np.ndarray, lado: str) -> float:
    _cargar_plantillas()
    plantillas = [h for nombre, h in _PLANTILLAS.items() if nombre.endswith(lado)]
    if not plantillas:
        return 0.0
    a, b = _huella(img), _huella(girada)
    normal = max(float((a * h).mean()) for h in plantillas)
    invertida = max(float((b * h).mean()) for h in plantillas)
    return float(np.clip((normal - invertida) / 0.3, -1, 1))


def _cargar_plantillas():
    global _PLANTILLAS
    if _PLANTILLAS is None:
        _PLANTILLAS = {ruta.stem: _huella(cv2.imread(str(ruta))) for ruta in PLANTILLAS_DIR.glob("*.png")}


def recortar_por_esquinas(foto: np.ndarray, puntos) -> np.ndarray:
    """Recorta y endereza la tarjeta con las 4 esquinas marcadas a mano (en cualquier orden)."""
    return _enderezar(foto, _ordenar(np.array(puntos, dtype=np.float32)))


def enderezar_cedula(foto: np.ndarray, lado: str) -> tuple[np.ndarray, bool, str] | None:
    """Recorta, endereza y orienta. Devuelve (imagen, seguro, nota) o None si no encontro la tarjeta."""
    recorte = recortar(foto)
    if recorte is not None and recorte.confianza >= CONFIANZA_MINIMA:
        imagen, nota = recorte.imagen, f"tarjeta encontrada {recorte.confianza:.0%}"
    elif ya_recortada(foto):
        # La tarjeta ocupa toda la foto (alguien ya la recorto): no hay borde que buscar, solo enderezar
        imagen = foto if foto.shape[1] >= foto.shape[0] else cv2.rotate(foto, cv2.ROTATE_90_CLOCKWISE)
        nota = "la foto ya estaba recortada"
    else:
        return None
    imagen, seguro = orientar(imagen, lado)
    return imagen, seguro, nota + ("" if seguro else ", orientacion dudosa")


def ya_recortada(foto: np.ndarray) -> bool:
    """True si la foto completa tiene la proporcion de una cedula (85,6 x 54 mm)."""
    alto, ancho = foto.shape[:2]
    return abs(max(alto, ancho) / min(alto, ancho) - PROPORCION) <= 0.12


def leer(datos: bytes) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)


def a_jpg(img: np.ndarray, calidad: int = 90, ancho_maximo: int = ANCHO_MAXIMO) -> bytes:
    """JPG de la cedula, reducido a un ancho que se lee perfecto (1800 px = ~530 dpi en una cedula)."""
    if img.shape[1] > ancho_maximo:
        img = cv2.resize(img, (ancho_maximo, round(img.shape[0] * ancho_maximo / img.shape[1])),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    return buf.tobytes()
