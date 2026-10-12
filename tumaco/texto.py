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


def mismo_documento(a: str, b: str) -> bool:
    """Mismo numero de documento, sin importar espacios o puntos: '59.675.754' = '59675754'."""
    da, db = re.sub(r"\D", "", str(a or "")), re.sub(r"\D", "", str(b or ""))
    return len(da) >= 5 and da == db


def reparar(texto: str) -> str:
    """Texto con letras danadas por mala codificacion ('QUIÃ‘ONES' -> 'QUIÑONES'); si no aplica, igual."""
    texto = str(texto or "")
    if "Ã" in texto or "Â" in texto:
        try:
            return texto.encode("cp1252").decode("utf-8")
        except UnicodeError:
            pass
    return texto


def sector(texto: str) -> str:
    """Sector del barrio segun una direccion o barrio: 'LIBERTAD', 'TRIUNFO', 'BRISAS' o '' si no se sabe.
    Hay numeros de casa repetidos en sectores distintos (Casa 61 de La Libertad y de El Triunfo)."""
    t = norm(texto)
    # La hoja a veces corta el barrio ('LA LIBERTA', 'BARRIO EL TRI')
    for clave, nombre in (("triunfo", "TRIUNFO"), ("el tri", "TRIUNFO"), ("liberta", "LIBERTAD"), ("brisas", "BRISAS"),
                          ("angeles", "BRISAS"), ("union victoria", "UNION VICTORIA")):
        if clave in t:
            return nombre
    return ""


def documento_distinto(a: str, b: str) -> bool:
    """Los dos documentos estan y son de personas distintas: no un error de digitacion de una o dos cifras
    ('5968887' por '59688887') ni un relleno ('00000000')."""
    da, db = re.sub(r"\D", "", str(a or "")), re.sub(r"\D", "", str(b or ""))
    if len(da) < 5 or len(db) < 5 or da == db or len(set(da)) == 1 or len(set(db)) == 1:
        return False
    return SequenceMatcher(None, da, db).ratio() < 0.8


def numeros_casa(texto: str) -> set:
    """Numeros de casa con su letra: 'Casa 298A' -> {('298', 'a')}, 'Casa 298 sector 1' -> {('298', ''), ('1', '')}."""
    return {(n.lstrip("0") or "0", letra)
            for n, letra in re.findall(r"(\d+)\s?([a-z])?(?![a-z0-9])", norm(str(texto or "")))}


def similitud_nombre(a: str, b: str) -> float:
    """Que tanto se parecen dos nombres (0 a 1), tolerando orden, tildes, errores de digitacion y
    letras que suenan igual (b/v, s/z/c, y/ll, h muda, letras dobles).

    Se mide sobre las palabras del nombre mas corto: 'Edison Erazo' vs 'EDISON ERAZO BERMUDEZ' = 1.0
    """
    pa = [p for p in re.findall(r"[a-zñ]+", norm(a)) if len(p) > 2]
    pb = [p for p in re.findall(r"[a-zñ]+", norm(b)) if len(p) > 2]
    if not pa or not pb:
        return 0.0
    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    puntos = sum(max(_parecido(p, q) for q in largo) for p in corto)
    return puntos / len(corto)


def fonetico(palabra: str) -> str:
    """Como suena la palabra en español: 'Yovana' y 'Giovanna', 'Zuñiga' y 'Suniga' quedan iguales."""
    p = norm(palabra).replace("ñ", "n")
    p = p.replace("ch", "#")  # la ch es un sonido propio; se protege antes de quitar la h
    p = re.sub(r"qu([ei])", r"k\1", p)
    p = re.sub(r"g([ei])", r"j\1", p)
    p = re.sub(r"gu([ei])", r"g\1", p)
    p = re.sub(r"c([ei])", r"s\1", p)
    p = p.replace("h", "").replace("ll", "y").replace("v", "b").replace("z", "s")
    p = p.replace("c", "k").replace("q", "k").replace("x", "s").replace("w", "u")
    p = re.sub(r"i(?=[aeou])", "y", p)  # 'Gio-vanna' ~ 'Yo-vana'
    p = re.sub(r"(.)\1+", r"\1", p)  # letras dobles: 'Giovanna' -> 'jyobana'
    return p.replace("#", "ch")


def _parecido(p: str, q: str) -> float:
    return max(SequenceMatcher(None, p, q).ratio(), SequenceMatcher(None, fonetico(p), fonetico(q)).ratio())


def terminos_busqueda_nombre(nombre: str, maximo: int = 6) -> list[str]:
    """Textos para buscar un nombre en el filtro de Kobo (que busca 'contiene').

    Un nombre puede estar escrito de muchas formas, asi que se busca por partes: primero las
    palabras completas (las mas largas, que son las mas raras) y luego sus primeras letras,
    que aguantan tildes y errores de digitacion al final. Cada fila encontrada se valida luego
    con similitud_nombre.
    """
    palabras = sorted({p.upper() for p in re.findall(r"[a-zñ]+", norm(nombre)) if len(p) > 2},
                      key=lambda p: (-len(p), p))
    terminos = palabras[:3] + [p[:4] for p in palabras[:3] if len(p) > 4]
    vistos, salida = set(), []
    for t in terminos:
        if t not in vistos:
            vistos.add(t)
            salida.append(t)
    return salida[:maximo]
