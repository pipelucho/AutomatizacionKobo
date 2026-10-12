import json
import re
import time
from dataclasses import dataclass

from playwright.sync_api import Error, Page, TimeoutError

from . import config
from .humano import clic, escribir, pausa
from .texto import digitos, mismo_documento, norm, numeros_casa, similitud_nombre, terminos_busqueda_nombre

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # tiempo para iniciar sesion a mano si hace falta
UMBRAL_NOMBRE = 0.6  # similitud minima del nombre para aceptar una fila sin preguntar
MARGEN_DECISION = 0.3  # ventaja minima de la mejor fila sobre la segunda para elegirla sin dudar

# Orden de busqueda propio de algunos formularios: (campo, posicion de su caja en la fila de filtros, 1 = primera)
# El formulario 1 no esta aqui: ubica sus columnas por el nombre del encabezado (config.KOBO_COLUMNA_*).
# Primero el documento (sale del formulario 1, columna I del Excel): es el dato mas seguro. Si la persona
# aun no lo tiene en el Excel, se empieza por la casa.
BUSQUEDA_POR_FILTRO = {
    config.FORMULARIOS[1]: [("documento", 14), ("casa", 16), ("usuario", 15), ("nombre", 13)],
    # Mismo orden que el 2; columnas de DATOS DEL USUARIO (la 11 es el nombre de la encuestadora, no del usuario)
    config.FORMULARIOS[2]: [("documento", 13), ("casa", 15), ("usuario", 14), ("nombre", 12)],
    # DATOS DEL USUARIO Y DEL INMUEBLE (la 9 es el nombre de quien hace el acta, no del usuario)
    config.FORMULARIOS[3]: [("documento", 11), ("casa", 13), ("usuario", 12), ("nombre", 10)],
}
CLAVES_COLUMNA = {
    "usuario": config.KOBO_COLUMNA_USUARIO,
    "casa": config.KOBO_COLUMNA_CASA,
    "nombre": config.KOBO_COLUMNA_NOMBRE,
}


@dataclass
class Coincidencia:
    indice: int  # posicion de la fila en la tabla filtrada (para abrirla despues)
    datos: dict  # {encabezado: valor}
    sim_nombre: float
    casa_ok: bool  # el numero de la casa coincide (298 con 298A cuenta)
    nombre: str = ""  # nombre de la persona atendida segun Kobo
    casa_exacta: bool = False  # la casa coincide tal cual (298 con 298A NO cuenta)
    usuario_ok: bool = False  # el No. de usuario coincide
    casa: str = ""  # direccion segun Kobo
    documento_ok: bool = False  # el documento coincide con el del formulario 1 (columna I del Excel)

    @property
    def puntaje(self) -> float:
        """Que tanto coincide con el Excel comparando nombre, usuario, casa y documento."""
        return (self.sim_nombre + (0.6 if self.usuario_ok else 0) + (0.6 if self.documento_ok else 0)
                + (0.4 if self.casa_exacta else 0.2 if self.casa_ok else 0))

    @property
    def confirmada(self) -> bool:
        """Hay evidencia suficiente de que es la persona del Excel.

        Nunca solo por el nombre: con nombres comunes (dos 'MARTHA CORTES') se editaba el registro de
        otra persona. Se pide nombre parecido y ademas usuario, casa o documento; o dos de esos tres.
        El documento solo tampoco basta (puede estar mal digitado en otra persona).
        """
        return ((self.sim_nombre >= UMBRAL_NOMBRE and (self.usuario_ok or self.casa_ok or self.documento_ok))
                or (self.usuario_ok and self.casa_exacta)
                or (self.documento_ok and (self.usuario_ok or self.casa_exacta)))


class Kobo:
    def __init__(self, page: Page):
        self.page = page
        self.base = config.KOBO_URL
        self.formulario = ""
        self.motivo = ""  # por que no se encontro al ultimo usuario buscado (se anota en el Excel)
        self._mapa_columnas = _cargar_mapa_columnas()
        self._url_datos: dict[str, str] = {}  # formulario -> URL de su pestana DATOS (para no navegar desde el inicio)

    # ---------- Sesion ----------

    def esta_logueado(self) -> bool:
        resp = self.page.request.get(f"{self.base}/me/")
        return resp.ok and bool(resp.json().get("username"))

    def iniciar_sesion(self):
        self.page.goto(f"{self.base}/accounts/login/")
        if self.esta_logueado():
            print("Sesion de Kobo ya activa.")
            self.page.goto(f"{self.base}/#/projects/home")
            return

        if config.KOBO_USER and config.KOBO_PASS:
            print("Iniciando sesion en Kobo con los datos del .env ...")
            escribir(self.page.locator('input[name="login"], input[name="username"]').first, config.KOBO_USER)
            escribir(self.page.locator('input[name="password"]').first, config.KOBO_PASS)
            clic(self.page.locator('button[type="submit"], input[type="submit"]').first)
        else:
            print("No hay KOBO_USER/KOBO_PASS en .env: inicia sesion manualmente en la ventana del navegador.")

        self.page.wait_for_url(lambda url: "/accounts/login" not in url, timeout=LOGIN_TIMEOUT_MS)
        if not self.esta_logueado():
            raise RuntimeError("No se pudo iniciar sesion en Kobo (revisa usuario/contrasena).")
        print("Sesion de Kobo iniciada.")

    # ---------- Navegacion por formulario ----------

    def abrir_datos(self, nombre: str):
        """Abre la tabla DATOS del formulario.

        La primera vez entra por 'Mis proyectos' y recuerda la URL; con los siguientes
        usuarios va directo a esa URL (mucho mas rapido que repetir toda la navegacion).
        """
        self.page.bring_to_front()  # Chrome no dibuja las pestanas en segundo plano
        url = self._url_datos.get(nombre)
        if not url:
            self.abrir_formulario(nombre)
            self.ir_a_datos()
            self._url_datos[nombre] = self.page.url
            return
        self.formulario = nombre
        print(f"Abriendo datos de: {nombre}")
        if self.page.url == url:
            self.page.reload()  # misma URL: recargar para empezar sin el filtro del usuario anterior
        else:
            self.page.goto(url)
        self.page.locator(".rt-tbody .rt-tr-group").first.wait_for(timeout=60_000)
        print("Esperando que cargue la tabla de datos...")
        self._esperar_red()
        self._esperar_tabla_estable()

    def cerrar_pestanas_extra(self):
        """Cierra las pestanas que no son la principal de Kobo (ej. ediciones que quedaron abiertas)."""
        for pagina in self.page.context.pages:
            if pagina is not self.page and not pagina.is_closed():
                pagina.close()
        self.page.bring_to_front()

    def abrir_formulario(self, nombre: str):
        """Desde 'Mis proyectos' da clic en el proyecto cuyo nombre empieza por `nombre`."""
        self.formulario = nombre
        self.page.goto(f"{self.base}/#/projects/home")
        enlace = self.page.get_by_role("link", name=re.compile("^" + re.escape(nombre), re.I)).first
        enlace.wait_for(timeout=30_000)
        print(f"Abriendo formulario: {nombre}")
        clic(enlace)
        self.page.wait_for_url(re.compile(r"#/forms/"), timeout=30_000)

    def ir_a_datos(self):
        """Clic en la pestana DATOS (3er item del menu del formulario) y espera la tabla."""
        tab = self.page.locator(".page-wrapper__content--form-landing > nav > ul > li:nth-child(3) a")
        tab.wait_for(timeout=30_000)
        pausa(self.page)
        clic(tab)
        self.page.wait_for_url(re.compile(r"/data"), timeout=30_000)
        self.page.locator(".rt-tbody .rt-tr-group").first.wait_for(timeout=60_000)
        print("Esperando que cargue la tabla de datos...")
        self._esperar_red()
        self._esperar_tabla_estable()

    # ---------- Busqueda del usuario ----------

    def buscar_usuario(self, usuario, etiqueta: str = "tabla") -> Coincidencia | None:
        """Busca al usuario filtrando la tabla de DATOS, en el orden propio de cada formulario.

        - Formulario 1: USUARIO, CASA y Nombre (columnas ubicadas por el nombre del encabezado).
        - Formularios en BUSQUEDA_POR_FILTRO: columnas fijas por la posicion de su caja de filtro.

        El filtro de Kobo es "contiene" (buscar 81 trae 810, 181, 781...), asi que cada fila
        se compara con los 3 datos del Excel (nombre, usuario y casa) y se elige sola la que
        mejor coincide. Si no se encuentra o hay duda, devuelve None y deja en self.motivo
        lo que paso (para anotarlo en el Excel).
        """
        self.motivo = ""
        tabla = self.leer_tabla()
        encabezados = tabla["encabezados"]
        plan = BUSQUEDA_POR_FILTRO.get(self.formulario)
        if plan:
            orden = [campo for campo, _ in plan]
            columnas = {campo: posicion - 1 for campo, posicion in plan}
            for campo, col in columnas.items():
                nombre_col = encabezados[col] if col < len(encabezados) else "(no existe)"
                print(f"   Columna para {campo.upper()}: [{col + 1}] {nombre_col}")
        else:
            orden = ["usuario", "casa", "nombre"]
            columnas = {campo: self._columna(encabezados, campo, CLAVES_COLUMNA[campo], preguntar=False)
                        for campo in orden}

        valores = {
            "documento": [getattr(usuario, "documento", "")],
            "usuario": [usuario.usuario],
            "casa": [usuario.casa],
            "nombre": terminos_busqueda_nombre(usuario.nombre),
        }
        n = 0
        mas_parecida, dudas = None, []
        for campo in orden:
            col = columnas.get(campo)
            if col is None and not plan:
                col = columnas[campo] = self._columna(encabezados, campo, CLAVES_COLUMNA[campo])
            if col is None:
                continue
            for valor in valores[campo]:
                if not valor:
                    continue
                n += 1
                print(f"\nIntento {n}: buscar '{valor}' por {campo.upper()}")
                self._guardar_debug(f"{etiqueta}_intento{n}", self.leer_tabla())
                if not self._filtrar(col, valor):
                    break
                tabla = self.leer_tabla()
                self._guardar_debug(f"{etiqueta}_intento{n}_filtrada", tabla)
                candidatas = self._candidatas(tabla, campo, col, valor, usuario, columnas)
                elegida, empatadas = self._decidir(candidatas)
                if elegida:
                    print(f"   Usuario encontrado en la fila {elegida.indice + 1}.")
                    return elegida
                for c in candidatas:
                    if mas_parecida is None or c.puntaje > mas_parecida.puntaje:
                        mas_parecida = c
                self._filtrar(col, "")
                if empatadas:  # registro repetido en Kobo: buscar por otro dato traeria lo mismo
                    dudas = empatadas
                    break
            if dudas:
                break

        if dudas:
            self.motivo = "Dudoso: varios registros iguales en Kobo (" + " / ".join(
                f"{c.nombre} {c.casa}".strip() for c in dudas[:3]) + ")"
        elif mas_parecida:
            self.motivo = (f"No encontrado: el mas parecido en Kobo es {mas_parecida.nombre} "
                           f"{mas_parecida.casa} ({mas_parecida.sim_nombre:.0%} de parecido en el nombre)").replace("  ", " ")
        else:
            self.motivo = f"No encontrado en Kobo por {', '.join(c.lower() for c in orden)}"
        print(f"\n{self.motivo}")
        return None

    def _candidatas(self, tabla: dict, campo: str, col: int, valor: str, usuario,
                    columnas: dict) -> list[Coincidencia]:
        """Filas de la tabla filtrada que de verdad coinciden con lo buscado, comparadas con el Excel."""
        encabezados = tabla["encabezados"]

        def celda(celdas, campo_col):
            i = columnas.get(campo_col)
            return celdas[i] if i is not None and i < len(celdas) else ""

        candidatas = []
        for i, celdas in enumerate(tabla["filas"]):
            buscada = celdas[col] if col < len(celdas) else ""
            if campo == "nombre":
                coincide = similitud_nombre(usuario.nombre, buscada) >= UMBRAL_NOMBRE
            elif campo == "documento":
                coincide = mismo_documento(valor, buscada)
            else:
                coincide = digitos(valor) in digitos(buscada, todos=True)
            if not coincide:
                continue
            nombre_kobo, casa_kobo, usuario_kobo = celda(celdas, "nombre"), celda(celdas, "casa"), celda(celdas, "usuario")
            documento_excel = getattr(usuario, "documento", "")
            candidatas.append(Coincidencia(
                indice=i,
                datos=dict(zip(encabezados, celdas)),
                sim_nombre=similitud_nombre(usuario.nombre, nombre_kobo),
                casa_ok=bool(usuario.casa) and digitos(usuario.casa) in digitos(casa_kobo, todos=True),
                nombre=nombre_kobo.strip(),
                casa_exacta=bool(numeros_casa(usuario.casa) & numeros_casa(casa_kobo)),
                usuario_ok=bool(usuario.usuario) and digitos(usuario.usuario) in digitos(usuario_kobo, todos=True),
                casa=casa_kobo.strip(),
                documento_ok=bool(documento_excel) and mismo_documento(documento_excel, celda(celdas, "documento")),
            ))

        criterio = "con nombre parecido a" if campo == "nombre" else "con valor exacto"
        print(f"   {len(tabla['filas'])} fila(s) en la tabla, {len(candidatas)} {criterio} '{valor}'.")
        candidatas.sort(key=lambda c: c.puntaje, reverse=True)
        for k, c in enumerate(candidatas[:10], start=1):
            print(f"   [{k}] {self._resumen(c)}")
        return candidatas

    @staticmethod
    def _decidir(candidatas: list[Coincidencia]) -> tuple[Coincidencia | None, list[Coincidencia]]:
        """Elige sola la fila que mejor coincide con el Excel en nombre, usuario y casa.

        Devuelve (elegida, []) si la mejor esta confirmada y claramente por encima de las demas,
        o (None, empatadas) si hay varias confirmadas casi iguales (ej. registro duplicado).
        """
        confirmadas = [c for c in candidatas if c.confirmada]
        if not confirmadas:
            return None, []
        mejor = confirmadas[0]
        empatadas = [c for c in confirmadas if mejor.puntaje - c.puntaje < MARGEN_DECISION]
        if len(empatadas) > 1:
            print(f"   [!] {len(empatadas)} registros coinciden casi igual: no se puede saber cual es.")
            return None, empatadas
        print(f"   Elegido: {mejor.nombre} | {mejor.casa} (el que mas coincide con el Excel)")
        return mejor, []

    @staticmethod
    def _resumen(c: Coincidencia) -> str:
        marcas = [m for m, ok in (("documento coincide", c.documento_ok), ("usuario coincide", c.usuario_ok),
                                  ("casa exacta" if c.casa_exacta else "casa parecida", c.casa_ok)) if ok]
        return " | ".join([c.nombre or "?", c.casa or "?", f"nombre {c.sim_nombre:.0%}", *marcas])

    # ---------- Edicion ----------

    def abrir_edicion(self, c: Coincidencia) -> Page:
        """Clic en el lapiz (3er boton de la primera columna) de la fila del usuario.

        Kobo abre el formulario de edicion (Enketo) en una pestana nueva; se devuelve esa pagina.
        """
        fila = self.page.locator(".rt-tbody .rt-tr-group").nth(c.indice)
        boton = fila.locator(".rt-td.rt-sub-actions button:nth-child(3)")
        print(f"Abriendo edicion de la fila {c.indice + 1}...")
        try:
            with self.page.context.expect_page(timeout=15_000) as nueva:
                clic(boton)
            edicion = nueva.value
        except TimeoutError:
            edicion = self.page  # se abrio en la misma pestana
        edicion.bring_to_front()
        edicion.wait_for_load_state("domcontentloaded")
        print("Esperando que cargue el formulario de edicion...")
        edicion.locator("form.or").first.wait_for(timeout=90_000)
        edicion.wait_for_timeout(2000)
        return edicion

    def enviar_edicion(self, edicion: Page) -> bool:
        """Clic en ENVIAR (#submit-form) para actualizar el registro en Kobo.

        Si el formulario tiene campos con error, los muestra y espera a que se corrijan a mano.
        Devuelve True si Kobo confirmo el envio.
        """
        while True:
            print("Enviando formulario a Kobo...")
            edicion.bring_to_front()
            # Tras generar el PDF (modo impresion), Enketo puede dejar oculto el boton ENVIAR:
            # Playwright no puede hacer clic en algo que no se ve, asi que se usa un clic por JavaScript
            boton = edicion.locator("#submit-form")
            try:
                boton.wait_for(state="visible", timeout=5_000)
                clic(boton)
            except TimeoutError:
                if not boton.count():
                    print("   No encontre el boton ENVIAR en el formulario.")
                    return False
                print("   (el boton ENVIAR esta oculto: se presiona por JavaScript)")
                boton.evaluate("b => b.click()")
            estado, mensaje = _esperar_resultado_envio(edicion)

            if estado == "ok":
                print(f"   Formulario actualizado en Kobo. {mensaje}".rstrip())
                return True
            if estado == "errores":
                print("   El formulario no se envio porque tiene campos con error:")
                for campo in mensaje:
                    print(f"     - {campo}")
            else:
                print(f"   Kobo respondio: {mensaje or 'sin respuesta'}")
            resp = input("   Corrige en el navegador y presiona Enter para reintentar (o escribe n para no enviar): ")
            if resp.strip().lower() == "n":
                return False

    # ---------- Tabla ----------

    def leer_tabla(self) -> dict:
        return self.page.evaluate(_JS_LEER_TABLA)

    def _filtrar(self, col: int, valor: str) -> bool:
        """Escribe `valor` en el filtro de la columna `col`.

        El id del filtro (#mantine-xxxx) cambia en cada carga, asi que se ubica
        por la posicion del encabezado de la columna.
        """
        if not self.page.evaluate(_JS_MARCAR_FILTRO, col):
            print("   No encontre la caja de filtro de esa columna.")
            return False
        filtro = self.page.locator("[data-tumaco-filtro]")
        antes = _firma_tabla(self.leer_tabla())
        if valor:
            escribir(filtro, valor)
        else:
            filtro.fill("")
        filtro.press("Enter")
        self._esperar_red()
        self._esperar_tabla_estable(antes)
        return True

    def _esperar_red(self, timeout_ms: int = 4_000):
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except TimeoutError:
            pass  # Kobo a veces mantiene conexiones abiertas; la tabla estable es lo que importa

    def _esperar_tabla_estable(self, antes: str | None = None, maximo_s: float = 10):
        """Espera a que la tabla termine de actualizarse en vez de una pausa fija.

        Termina cuando dos lecturas seguidas son iguales y (si se indica) distintas de `antes`;
        si la tabla no cambia (el filtro dio lo mismo), acepta que este estable tras ~2.5 s.
        """
        inicio = time.monotonic()
        ultima = None
        while time.monotonic() - inicio < maximo_s:
            self.page.wait_for_timeout(400)
            actual = _firma_tabla(self.leer_tabla())
            if actual == ultima and (antes is None or actual != antes or time.monotonic() - inicio > 2.5):
                return
            ultima = actual

    def _columna(self, encabezados: list[str], campo: str, clave: str, preguntar: bool = True) -> int | None:
        """Indice de la columna para `campo`.

        `clave` admite varios terminos separados por '+' que deben estar todos en el
        encabezado (ej. 'persona atendida+nombre'). Si no se puede decidir, pregunta y
        recuerda la respuesta en columnas.json para este formulario.
        """
        guardado = self._mapa_columnas.get(self.formulario, {}).get(campo)
        if guardado in encabezados:
            return encabezados.index(guardado)

        terminos = [norm(t) for t in clave.split("+") if t.strip()]
        exactas = [i for i, h in enumerate(encabezados) if norm(h) == terminos[0]] if len(terminos) == 1 else []
        parciales = [i for i, h in enumerate(encabezados) if all(t in norm(h) for t in terminos)]
        opciones = exactas or parciales
        if opciones:
            # Si hay varias (ej. 'PERSONA ATENDIDA / Nombre' aparece tambien en la firma) se usa la primera
            return opciones[0]
        if not preguntar:
            return None

        print(f"\n   ¿Cual columna corresponde a {campo.upper()} en '{self.formulario}'?")
        lista = opciones or range(len(encabezados))
        for i in lista:
            print(f"     [{i}] {encabezados[i]}")
        resp = input("   Numero de la columna (Enter para omitir): ").strip()
        if not resp.isdigit() or int(resp) >= len(encabezados):
            return None
        col = int(resp)
        self._mapa_columnas.setdefault(self.formulario, {})[campo] = encabezados[col]
        _guardar_mapa_columnas(self._mapa_columnas)
        return col

    def _guardar_debug(self, etiqueta: str, tabla: dict):
        config.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (config.DEBUG_DIR / f"{etiqueta}.json").write_text(
            json.dumps(tabla, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        if not config.DEBUG_CAPTURAS:
            return  # las capturas de pantalla completa son lentas; activar con DEBUG_CAPTURAS=1
        try:
            self.page.screenshot(path=str(config.DEBUG_DIR / f"{etiqueta}.png"), timeout=10_000)
        except TimeoutError:
            print("   (no se pudo tomar la captura de depuracion; se continua)")


def _firma_tabla(tabla: dict) -> str:
    return json.dumps(tabla.get("filas", []), ensure_ascii=False)


def _cargar_mapa_columnas() -> dict:
    if config.COLUMNAS_PATH.exists():
        return json.loads(config.COLUMNAS_PATH.read_text(encoding="utf-8"))
    return {}


def _esperar_resultado_envio(edicion: Page, limite_s: int = 120):
    """Espera la respuesta de Kobo tras ENVIAR.

    Devuelve ("ok", texto), ("errores", [campos]) o ("desconocido", texto).
    """
    exito = ("exito", "éxito", "exitosamente", "enviado", "submitted", "success", "guardado",
             "gracias por participar", "thank you")
    # Aviso intermedio de Kobo antes de redirigir a /thanks: el envio sigue en curso, no es la respuesta final
    en_curso = ("redirigido", "redirected", "enviando", "submitting")
    for _ in range(limite_s * 2):
        try:
            if edicion.is_closed():
                return "ok", "(Kobo cerro la pestaña de edicion)"
            if "/thanks" in edicion.url or "/edit/" not in edicion.url:
                return "ok", f"(Kobo confirmo el envio: {edicion.url})"
            dialogo = edicion.locator(".vex-dialog-message")
            if dialogo.count() and dialogo.first.is_visible():
                texto = " ".join(dialogo.first.inner_text().split())
                aceptar = edicion.locator(".vex-dialog-buttons .btn-primary")
                if aceptar.count() and aceptar.first.is_visible():
                    pausa(edicion, 0.5, 1.0)
                    clic(aceptar.first)
                if any(p in norm(texto) for p in map(norm, en_curso)):
                    edicion.wait_for_timeout(500)
                    continue  # esperar la redireccion a /thanks
                return ("ok" if any(p in norm(texto) for p in map(norm, exito)) else "desconocido"), texto
            errores = edicion.evaluate(_JS_CAMPOS_CON_ERROR)
            if errores:
                return "errores", errores
            edicion.wait_for_timeout(500)
        except Error as e:
            # La pagina se esta redirigiendo (contexto destruido): se revisa de nuevo en la siguiente vuelta
            if "closed" in str(e).lower():
                return "ok", "(Kobo cerro la pestaña de edicion)"
            edicion.wait_for_timeout(500)
    return "desconocido", f"No hubo respuesta en {limite_s} s"


# Preguntas visibles que Enketo marco como obligatorias sin responder o con valor no valido
_JS_CAMPOS_CON_ERROR = r"""
() => [...document.querySelectorAll('.question.invalid-required, .question.invalid-constraint')]
  .filter(q => q.offsetParent !== null)
  .map(q => ((q.querySelector('.question-label') || q).innerText || '').trim().split('\n')[0])
"""


def _guardar_mapa_columnas(mapa: dict):
    config.COLUMNAS_PATH.write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")


# Encabezados (texto completo, aunque en pantalla se vea cortado) y celdas de cada fila.
_JS_LEER_TABLA = r"""
() => {
  const limpiar = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  let ths = [...document.querySelectorAll('.rt-thead.-header .rt-th')];
  let filas = [...document.querySelectorAll('.rt-tbody .rt-tr-group')]
    .map(g => [...g.querySelectorAll('.rt-td')].map(limpiar));
  if (!ths.length) {
    ths = [...document.querySelectorAll('thead tr:first-child th, [role="columnheader"]')];
    filas = [...document.querySelectorAll('tbody tr, [role="rowgroup"] [role="row"]')]
      .filter(f => !f.querySelector('[role="columnheader"]'))
      .map(f => [...f.querySelectorAll('td, [role="cell"], [role="gridcell"]')].map(limpiar));
  }
  return {
    encabezados: ths.map(limpiar),
    filas: filas.filter(c => c.some(t => t && t !== '-')),
  };
}
"""

# Marca con data-tumaco-filtro la caja de texto que queda debajo del encabezado `col`.
_JS_MARCAR_FILTRO = r"""
(col) => {
  document.querySelectorAll('[data-tumaco-filtro]').forEach(e => e.removeAttribute('data-tumaco-filtro'));
  const celda = document.querySelector(`.rt-thead.-filters > div > div:nth-child(${col + 1})`);
  const directo = celda && celda.querySelector('input:not([type=checkbox]):not([type=radio]):not([type=hidden])');
  if (directo) {
    celda.scrollIntoView({ inline: 'center', block: 'nearest' });
    directo.setAttribute('data-tumaco-filtro', '1');
    return true;
  }
  let ths = [...document.querySelectorAll('.rt-thead.-header .rt-th')];
  if (!ths.length) ths = [...document.querySelectorAll('thead tr:first-child th, [role="columnheader"]')];
  const th = ths[col];
  if (!th) return false;
  th.scrollIntoView({ inline: 'center', block: 'nearest' });
  const r = th.getBoundingClientRect();
  const input = [...document.querySelectorAll('input')]
    .filter(i => !['checkbox', 'radio', 'hidden'].includes(i.type))
    .find(i => {
      const ri = i.getBoundingClientRect();
      const cx = ri.left + ri.width / 2;
      return ri.width > 0 && cx >= r.left && cx <= r.right && ri.top >= r.top - 5;
    });
  if (!input) return false;
  input.setAttribute('data-tumaco-filtro', '1');
  return true;
}
"""
