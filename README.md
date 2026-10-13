# Automatización Kobo – Tumaco

Bot que revisa y corrige los 4 formularios de KoboToolbox de cada usuario de la lista (Excel), guarda los PDF de
cada formulario y el PDF unido en `CONTINGENCIAL/<USUARIO>_<NOMBRE>/` y llena su fila en la hoja de Google
(o, en el procesamiento aparte, en un Excel local).

## Cómo instalarlo y correrlo en otro computador

### 1. Lo que debe tener instalado
- **Windows** con **Google Chrome** (en la ruta normal `C:\Program Files\Google\Chrome\`).
- **Python 3.12**: <https://www.python.org/downloads/> (al instalar, marcar *Add python.exe to PATH*).
- **Git**: <https://git-scm.com/download/win>.

### 2. Clonar el repositorio
En Git Bash, en la carpeta donde lo quiera guardar:

```bash
git clone https://github.com/pipelucho/AutomatizacionKobo.git
cd AutomatizacionKobo
```

### 3. Crear el entorno de Python e instalar las librerías
En PowerShell o CMD, dentro de la carpeta `AutomatizacionKobo`:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-herramientas.txt
```

El bot usa el Google Chrome instalado (no hace falta `playwright install`).

### 4. Configurar el `.env` (usuario y contraseña de Kobo)
Copiar el ejemplo y completarlo:

```bash
copy .env.example .env
```

Abrir `.env` con el Bloc de notas y escribir `KOBO_USER` y `KOBO_PASS`. **El `.env` nunca se sube a GitHub**
(está en `.gitignore`): cada computador tiene el suyo.

### 5. Archivos que NO vienen en el repositorio (pedirlos aparte)
Tienen datos de personas, por eso no están en GitHub. Copiarlos en la carpeta del proyecto:

| Archivo o carpeta | Para qué |
|---|---|
| `firmas/contratista.json` y `firmas/jhon.json` | Trazos de las firmas del contratista (Adriana Muñoz en F1-F3, Jhon en F4). Sin ellos el bot no puede firmar. |
| `USUARIOS.xlsx` | Lista de personas a procesar (columna A nombre, B usuario, C casa; el bot llena el resto). |
| `USUARIOS_APARTE.xlsx`, `HOJA_APARTE.xlsx`, `ENTRADA_APARTE/` | Solo para el procesamiento aparte (ver abajo). |

### 6. La hoja de Google (solo para `main.py`)
El bot escribe en la hoja a través de un Chrome aparte que se abre con:

```bash
powershell -ExecutionPolicy Bypass -File herramientas\abrir_chrome_hoja.ps1
```

La primera vez, iniciar sesión en Google en esa ventana. Dejarla abierta mientras corre el bot.

### 7. Ejecutar

```bash
.venv\Scripts\python main.py --limite 1
```

- `--limite 1` hace una prueba con la primera persona pendiente; sin él procesa todas.
- `--usuarios 733,785` procesa solo esos números de usuario.
- La primera vez, el bot abre su propio Chrome e inicia sesión en Kobo con los datos del `.env`.
- Durante la corrida aparecen **ventanas en el navegador del bot** para decidir (soporte de propiedad, nombre,
  cédula, etc.): responderlas para que siga.

**Procesamiento aparte** (sin tocar la hoja de Google; lo de la hoja queda en `HOJA_APARTE.xlsx` con la columna
RESPONSABLE en blanco, y la cédula y la factura de `ENTRADA_APARTE/<usuario>/` reemplazan las de Kobo):

```bash
.venv\Scripts\python herramientas\agregar_aparte.py --usuario 123 --casa 45 --nombre "NOMBRE COMO EN LA CEDULA" --documento 12345678 --cara cara.jpg --reverso reverso.jpg --factura factura.jpg
.venv\Scripts\python aparte.py
```

### 8. Dónde quedan los resultados
- `CONTINGENCIAL/<USUARIO>_<NOMBRE>/`: PDF de cada formulario, `DOCUMENTO.pdf` (cédula) y el PDF unido
  (`CONTINGENCIAL_APARTE/` en el procesamiento aparte).
- `CASOS.xlsx`: lo que quedó por resolver (no encontrados, sin formulario 4, cédulas a mano...).
- `salida/logs/`: todo lo que se vio en la terminal en cada corrida.

### Cuidados
- **Cerrar los Excel** (`USUARIOS.xlsx`, etc.) antes de correr el bot.
- **No correr dos veces a la vez**: el Chrome del bot usa un perfil propio (`.browser_profile`) que solo un proceso
  puede abrir.
- La cuenta de Kobo la usan varias personas: si alguien edita el mismo registro, Kobo responde *"Record is already
  being edited"*; esperar unos minutos.
- No subir a GitHub el `.env`, los Excel, `firmas/`, `CONTINGENCIAL/`, `salida/` ni `.browser_profile/`
  (ya están en `.gitignore`).
