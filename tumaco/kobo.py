import json
import re
from dataclasses import dataclass

from playwright.sync_api import Page, TimeoutError

from . import config
from .humano import clic, escribir, pausa
from .texto import digitos, norm, similitud_nombre

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # tiempo para iniciar sesion a mano si hace falta
UMBRAL_NOMBRE = 0.6  # similitud minima del nombre para aceptar una fila sin preguntar


@dataclass
class Coincidencia:
    indice: int  # posicion de la fila en la tabla filtrada (para abrirla despues)
    datos: dict  # {encabezado: valor}
    sim_nombre: float
    casa_ok: bool
    nombre: str = ""  # nombre de la persona atendida segun Kobo


class Kobo:
    def __init__(self, page: Page):
        self.page = page
        self.base = config.KOBO_URL
        self.formulario = ""
        self._mapa_columnas = _cargar_mapa_columnas()

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
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(4000)

    # ---------- Busqueda del usuario ----------

    def buscar_usuario(self, usuario, etiqueta: str = "tabla") -> Coincidencia | None:
        """Busca al usuario: primero por USUARIO, luego por CASA y por ultimo por Nombre.

        El filtro de Kobo es "contiene" (buscar 81 trae 810, 181, 781...), asi que cada fila
        se valida: el valor debe ser exacto en esa columna y el nombre (o la casa) debe
        parecerse al del Excel.
        """
        intentos = [
            ("usuario", config.KOBO_COLUMNA_USUARIO, usuario.usuario),
            ("casa", config.KOBO_COLUMNA_CASA, usuario.casa),
            # El filtro busca el texto tal cual, asi que se filtra por el ultimo apellido
            # y luego se compara el nombre completo
            ("nombre", config.KOBO_COLUMNA_NOMBRE, (usuario.nombre.split() or [""])[-1]),
        ]
        for n, (campo, clave, valor) in enumerate(intentos, start=1):
            if not valor:
                continue
            print(f"\nIntento {n}: buscar '{valor}' por {campo.upper()}")
            tabla = self.leer_tabla()
            self._guardar_debug(f"{etiqueta}_intento{n}", tabla)
            col = self._columna(tabla["encabezados"], campo, clave)
            if col is None or not self._filtrar(col, valor):
                continue

            tabla = self.leer_tabla()
            self._guardar_debug(f"{etiqueta}_intento{n}_filtrada", tabla)
            elegida = self._elegir_fila(tabla, campo, col, valor, usuario)
            if elegida:
                print(f"   Usuario encontrado en la fila {elegida.indice + 1}.")
                return elegida
            self._filtrar(col, "")
        print("\nNo se encontro al usuario por USUARIO, CASA ni Nombre.")
        return None

    def _elegir_fila(self, tabla: dict, campo: str, col: int, valor: str, usuario) -> Coincidencia | None:
        encabezados = tabla["encabezados"]
        col_nombre = self._columna(encabezados, "nombre", config.KOBO_COLUMNA_NOMBRE, preguntar=False)
        col_casa = self._columna(encabezados, "casa", config.KOBO_COLUMNA_CASA, preguntar=False)

        candidatas = []
        for i, celdas in enumerate(tabla["filas"]):
            celda = celdas[col] if col < len(celdas) else ""
            if campo == "nombre":
                exacto = similitud_nombre(usuario.nombre, celda) >= UMBRAL_NOMBRE
            else:
                exacto = digitos(valor) in digitos(celda, todos=True)
            if not exacto:
                continue
            nombre_kobo = celdas[col_nombre] if col_nombre is not None and col_nombre < len(celdas) else ""
            casa_kobo = celdas[col_casa] if col_casa is not None and col_casa < len(celdas) else ""
            candidatas.append(Coincidencia(
                indice=i,
                datos=dict(zip(encabezados, celdas)),
                sim_nombre=similitud_nombre(usuario.nombre, nombre_kobo),
                casa_ok=bool(usuario.casa) and digitos(usuario.casa) in digitos(casa_kobo, todos=True),
                nombre=nombre_kobo.strip(),
            ))

        total = len(tabla["filas"])
        print(f"   {total} fila(s) en la tabla, {len(candidatas)} con valor exacto '{valor}'.")
        if not candidatas:
            return None

        candidatas.sort(key=lambda c: (c.sim_nombre + (0.5 if c.casa_ok else 0)), reverse=True)
        fuertes = [c for c in candidatas if c.sim_nombre >= UMBRAL_NOMBRE or c.casa_ok]
        if len(fuertes) == 1:
            c = fuertes[0]
            print(f"   Coincide: {self._resumen(c, col_nombre, col_casa, encabezados)}")
            return c

        # Ninguna o varias parecidas: decide el usuario
        print(f"   Excel: {usuario.nombre} | USUARIO {usuario.usuario} | CASA {usuario.casa}")
        for k, c in enumerate(candidatas[:15], start=1):
            print(f"   [{k}] {self._resumen(c, col_nombre, col_casa, encabezados)}")
        resp = input("   ¿Cual es el usuario correcto? (numero, o 0 si ninguno): ").strip()
        if resp.isdigit() and 1 <= int(resp) <= len(candidatas[:15]):
            return candidatas[int(resp) - 1]
        return None

    @staticmethod
    def _resumen(c: Coincidencia, col_nombre, col_casa, encabezados) -> str:
        nombre = c.datos.get(encabezados[col_nombre], "?") if col_nombre is not None else "?"
        casa = c.datos.get(encabezados[col_casa], "?") if col_casa is not None else "?"
        return (f"{nombre} | {casa} | similitud nombre {c.sim_nombre:.0%}"
                f"{' | casa coincide' if c.casa_ok else ''}")

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
            clic(edicion.locator("#submit-form"))
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
        if valor:
            escribir(filtro, valor)
        else:
            filtro.fill("")
        filtro.press("Enter")
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(3000)
        return True

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
        self.page.screenshot(path=str(config.DEBUG_DIR / f"{etiqueta}.png"), full_page=True)


def _cargar_mapa_columnas() -> dict:
    if config.COLUMNAS_PATH.exists():
        return json.loads(config.COLUMNAS_PATH.read_text(encoding="utf-8"))
    return {}


def _esperar_resultado_envio(edicion: Page, limite_s: int = 120):
    """Espera la respuesta de Kobo tras ENVIAR.

    Devuelve ("ok", texto), ("errores", [campos]) o ("desconocido", texto).
    """
    exito = ("exito", "éxito", "exitosamente", "enviado", "submitted", "success", "guardado")
    for _ in range(limite_s * 2):
        if edicion.is_closed():
            return "ok", "(Kobo cerro la pestaña de edicion)"
        dialogo = edicion.locator(".vex-dialog-message")
        if dialogo.count() and dialogo.first.is_visible():
            texto = " ".join(dialogo.first.inner_text().split())
            aceptar = edicion.locator(".vex-dialog-buttons .btn-primary")
            if aceptar.count():
                pausa(edicion, 0.5, 1.0)
                clic(aceptar.first)
            return ("ok" if any(p in norm(texto) for p in map(norm, exito)) else "desconocido"), texto
        errores = edicion.evaluate(_JS_CAMPOS_CON_ERROR)
        if errores:
            return "errores", errores
        if "/edit/" not in edicion.url:
            return "ok", f"(redirigio a {edicion.url})"
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
