"""Saber si la firma que tiene hoy un formulario en Kobo es la que dibuja el bot (para no volver a firmar).

Se compara la tinta de la imagen de Kobo con los trazos del bot (firmas/*.json) dibujados aparte:
- se recortan ambas al borde de la tinta y se llevan al mismo tamano (no importa el tamano del lienzo);
- las proporciones (ancho/alto) deben ser parecidas: una firma cortada por la ventana pequena no lo es;
- la tinta de cada una debe caer sobre la de la otra (con un margen de unos pixeles).
"""
import json
import math

import cv2
import numpy as np

from . import config

ANCHO, ALTO = 300, 100  # tamano al que se llevan las dos firmas para compararlas
UMBRAL = 0.9  # firmas del bot: 100%; firmas de campo u otros equipos: 45-72% (calibrado el 12-oct)
MAX_DIFERENCIA_PROPORCION = 0.2  # |log(proporcion Kobo / proporcion bot)|


def _tinta(img: np.ndarray) -> np.ndarray | None:
    """Mascara de la tinta recortada a su borde (None si no hay tinta)."""
    if img.ndim == 3 and img.shape[2] == 4:  # PNG con transparencia: la tinta es lo opaco y oscuro
        gris = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
        mascara = (img[:, :, 3] > 64) & (gris < 160)
    else:
        gris = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mascara = gris < 160
    filas, columnas = np.where(mascara)
    if len(filas) < 30:  # lienzo vacio o solo una mancha
        return None
    return mascara[filas.min():filas.max() + 1, columnas.min():columnas.max() + 1].astype(np.uint8)


def _normalizar(mascara: np.ndarray) -> np.ndarray:
    return (cv2.resize(mascara * 255, (ANCHO, ALTO), interpolation=cv2.INTER_AREA) > 40).astype(np.uint8)


def plantilla(archivo_trazos: str) -> np.ndarray:
    """La firma del bot dibujada aparte desde sus trazos (mascara recortada a la tinta)."""
    firma = json.loads((config.FIRMAS_DIR / archivo_trazos).read_text(encoding="utf-8"))
    ancho = 800
    alto = max(1, round(ancho * firma["alto"] / firma["ancho"]))
    lienzo = np.zeros((alto + 20, ancho + 20), np.uint8)
    for trazo in firma["trazos"]:
        puntos = np.array([[10 + x * ancho, 10 + y * alto] for x, y in trazo], np.int32)
        cv2.polylines(lienzo, [puntos], False, 1, thickness=5)
    return _tinta(np.where(lienzo > 0, 0, 255).astype(np.uint8))


def parecido(imagen: bytes, archivo_trazos: str) -> tuple[float, str]:
    """(parecido de 0 a 1, explicacion) entre la firma de Kobo y la del bot."""
    img = cv2.imdecode(np.frombuffer(imagen, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return 0.0, "la imagen de la firma no se pudo leer"
    kobo, bot = _tinta(img), plantilla(archivo_trazos)
    if kobo is None:
        return 0.0, "la firma esta vacia"
    proporcion = abs(math.log((kobo.shape[1] / kobo.shape[0]) / (bot.shape[1] / bot.shape[0])))
    if proporcion > MAX_DIFERENCIA_PROPORCION:
        return 0.0, f"otra forma (proporcion distinta: {proporcion:.2f}); puede ser otra firma o una cortada"
    a, b = _normalizar(kobo), _normalizar(bot)
    nucleo = np.ones((7, 7), np.uint8)
    a_en_b = (a & cv2.dilate(b, nucleo)).sum() / max(1, a.sum())
    b_en_a = (b & cv2.dilate(a, nucleo)).sum() / max(1, b.sum())
    valor = (a_en_b + b_en_a) / 2
    return valor, f"parecido {valor:.0%}"


def es_la_del_bot(imagen: bytes | None, archivo_trazos: str) -> tuple[bool, str]:
    if not imagen:
        return False, "no tiene firma"
    valor, explicacion = parecido(imagen, archivo_trazos)
    return valor >= UMBRAL, explicacion
