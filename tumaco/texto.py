import re
import unicodedata
from difflib import SequenceMatcher


def norm(texto: str) -> str:
    """Minusculas, sin tildes, sin ':' ni '*', espacios simples."""
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", re.sub(r"[:*]", "", texto)).strip()


def digitos(texto: str, todos: bool = False):
    """Numeros contenidos en el texto. 'Casa 438' -> '438'; con todos=True -> ['438']."""
    nums = [n.lstrip("0") or "0" for n in re.findall(r"\d+", str(texto or ""))]
    return nums if todos else (nums[0] if nums else "")


def similitud_nombre(a: str, b: str) -> float:
    """Que tanto se parecen dos nombres (0 a 1), tolerando orden, tildes y errores de digitacion.

    Se mide sobre las palabras del nombre mas corto: 'Edison Erazo' vs 'EDISON ERAZO BERMUDEZ' = 1.0
    """
    pa = [p for p in re.findall(r"[a-zñ]+", norm(a)) if len(p) > 2]
    pb = [p for p in re.findall(r"[a-zñ]+", norm(b)) if len(p) > 2]
    if not pa or not pb:
        return 0.0
    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    puntos = sum(max(SequenceMatcher(None, p, q).ratio() for q in largo) for p in corto)
    return puntos / len(corto)
