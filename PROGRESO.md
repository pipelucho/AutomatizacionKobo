# Progreso del bot Tumaco — guardado el 12-oct-2026

> Archivo local (no va a git: tiene nombres y documentos). Al volver, empezar por **Pendientes**.

## Estado actual

- `USUARIOS.xlsx`: 58 personas.
  - **37 terminadas sin problemas** → sus carpetas estan en `CONTINGENCIAL\TERMINADOS` (24 con los 4 formularios, 13 sin formulario 4 en Kobo).
  - 11 con carpeta y algo pendiente (siguen en `CONTINGENCIAL`).
  - 10 sin procesar (sin carpeta).
- Hoja de Google "Tumaco": llena para todas las terminadas.
- Codigo guardado en git (ultimo commit: "Ventana del documento anexo con giro, soportes de la hoja y carpeta TERMINADOS").
- Verificado en la ultima corrida (`salida\logs\corrida_2026-10-12_04-32.log`):
  - el envio ya no se queda 30 s esperando (todos los envios 1–3 s);
  - el boton de girar funciono en real (843: girado 270° y vuelto a subir).

## Lista nueva de El Triunfo (12-oct, segunda parte)

- Lista de 19 usuarios (imagen) pasada a `CANDIDATOS.xlsx`; organizada y con decisiones en `USUARIOS_NUEVOS.xlsx`.
- Busqueda en Kobo y comparacion con la hoja, revisada caso por caso contigo:
  - **6 elegibles agregados a `USUARIOS.xlsx` (filas 60 a 65):** 49, 18, 75, 1, 247 y 74.
    - 247 y 74 no estaban en la lista.
    - 75: usar el juego de registros de usuario 75 y Casa 52A (en la ventana elegir el de la 52A); el de usuario 342 es duplicado.
    - 1: se procesa con los registros de Karyn Evelyn Nogales Marinez (poseedora).
  - **Apartados para revisar despues con detalle (quien atiende = "Otro"):** 320, 299, 304, 57.
  - **No elegibles:** 291 (solo F1), 78 (solo F4), 44, 97, 84, 101, 98, 66 (solo F4) y 22, 19, 65 (sin formularios).
- Columna K de la hoja: sigue KAREN QUIÑONES.
- Siguiente paso: correr el bot (`main.py --limite 10`), que toma a 885 (desde el F2) y a estos 6.

## Revision de las 16 carpetas que quedaban en CONTINGENCIAL (12-oct)

- Las 37 terminadas antes estan en `CONTINGENCIAL\TERMINADOS\CARGADOS` (las moviste tu).
- **Movidas a TERMINADOS (12), realizadas y con sus registros correctos en Kobo (usuario coincide):** 459, 483, 498, 505, 812 (no estan en USUARIOS.xlsx, eran de pruebas iniciales), 536, 633, 656, 690, 751, 783, 802.
- **Siguen en CONTINGENCIAL:** 581, 648, 843 (nombres a corregir) y 885 (incompleta, en cola del bot).
- Verificacion campo por campo Kobo vs hoja de las 12: 10 OK. **Devueltas a CONTINGENCIAL:**
  - 783: su F2 (826845937) tiene el documento 1087126583, que es de Maria Lorena Caicedo Calzada (usuario 467); revisar la cedula del F2.
  - 459: su F4 (829274156) dice usuario 452 y documento 5968887 (le falta un digito); el resto bien.
- 536: el analisis propone volver la casa del F4 a '60C' (valor original), pero F1-F3 y la hoja dicen 127: se deja 127.
- No se revisaron uno a uno los PDF por dentro (firma, cedula), solo que el PDF unido tenga todas las paginas.
- **Decidiste reprocesar las 12 con main.py:** carpetas devueltas a CONTINGENCIAL (TERMINADOS solo tiene CARGADOS); en USUARIOS.xlsx se borraron D-G y K de 802, 783, 751, 536, 633, 690 y 656, y se agregaron 459, 483, 498, 505 y 812 (filas 66-70). Quedan 19 pendientes para el bot.
- Corrida 10:23 (detenida por ti en 633): Kobo cambio el orden de las columnas de la tabla del formulario 4 y el bot buscaba en Barrio/Celular/Ubicacion/Muros (no marco nada falso: se detuvo con error). **Arreglado:** los formularios 2-4 ubican sus columnas por el titulo, no por la posicion (probado en solo lectura con 536 en F2, F3 y F4). Los 14 formularios 4 'No encontrado' de corridas anteriores se confirmaron por la API: ninguno existe. 802, 783, 751 y 536 quedaron con F1-F3 hechos y siguen desde el F4.
- Cambios del bot (aplican desde la corrida siguiente a la de 10:23+):
  - Ventana maximizada al abrir cada formulario (en ventana pequena el lienzo de la firma quedaba cortado y la firma podia salir incompleta). Pendiente: revisar las firmas del contratista ya hechas.
  - NO. USUARIO en los 4 formularios: si esta vacio se llena con el usuario del Excel (= hoja); si tiene otro numero, ventana para decidir (propone el del Excel, editable, o "Dejar lo de Kobo").
  - Pendiente al terminar la corrida: llenar por API/correccion puntual los NO. USUARIO vacios o distintos de los ya procesados y revisar las firmas del contratista.
- **No volver a firmar:** antes de borrar la firma del contratista, el bot descarga por la API la que tiene el registro y la compara con sus trazos (`tumaco/firmas.py`). Si es la del bot y esta completa (parecido >= 90%) no firma; si esta vacia, es otra o quedo cortada, la rehace. Calibrado: firmas del bot 100%, de campo u otros equipos 45-72%. Probado en solo lectura con 5 registros.
- Nombres corregidos con la cedula: 581 VERONICA PATRICIA ARIZALA CAICEDO, 648 ROCIO DEL PILAR CIFUENTES SALAZAR, 843 FELISA CECILIA QUIÑONES LANDAZURI (Excel y carpetas; los PDF unidos viejos se guardaron aparte).
- **Reproceso de todo CONTINGENCIAL:** marcas D-G y K borradas de 18, 49, 536, 581, 633, 648, 656, 690, 751, 783, 802, 843, 885. Quedan 22 pendientes (con 75, 1, 247, 74, 459, 483, 498, 505, 812).
- **Corrida 10:58 (primer lote de 10: 802, 783, 751, 536, 633, 690, 656, 648, 581, 885):** todos enviados y con la hoja llena; 35 firmas detectadas como del bot (no se volvio a firmar ninguna); 648 F3 usuario 649 -> 648 por la ventana; 648 y 581 con el nombre completo en Kobo y la hoja. Faltan 12: 843, 49, 18, 75, 1, 247, 74, 459, 483, 498, 505, 812.
- Los 9 correctos del lote (802, 751, 536, 633, 690, 656, 648, 581, 885) movidos a `TERMINADOS` (listos para cargar).
- **Nueva carpeta `CONTINGENCIAL\POR CORREGIR`** (con LEEME.txt): procesados con algo que corregir aparte; terminados.py no los saca de ahi. Hoy: 783 (F2 con documento de otra persona). Despues de su corrida va 459 (documento del F4 sin un digito).
- Despues de la corrida: corregir aparte lo que el bot no toca (usuario y documento): F4 de 459 (usuario 452 / doc 5968887) y F2 de 783 (doc de otra persona); y los 3 F4 de otras personas danados.
- **Formularios 4 de OTRAS personas que el bot edito por error** (fallo antiguo de buscar solo por nombre; no hay log del valor original):
  | F4 _id | De quien es (por su cedula y la hoja) | Que quedo mal | Correccion propuesta |
  |---|---|---|---|
  | 826863709 | Maria Enid Arias Jaramillo (doc 59665744, Casa 87; en F1/F3 es usuario 308, el F4 dice 208) | nombre y nombre de firma = 'MARIA LORENA ARBOLEDA REINA' | MARIA ENID ARIAS JARAMILLO |
  | 826867885 | Maria Zaida Cortes (usuario 296, doc 27128503, CS 125A) | nombre y firma = 'MARTHA CORTES'; casa 'CASA 125' | MARIA ZAIDA CORTES; casa 125A |
  | 829274695 | Paula Yolima Wisamano, su segunda casa (usuario 763, CS 521) | direccion = 'CASA 543' (la de su usuario 751) | CASA 521 |
- **Posibles elegibles nuevos encontrados de paso:** 763 (Paula, CS 521: F1-F3 sin procesar), 864 (Felisa Cecilia Quiñones Landazuri, Casa 593: F1-F3 sin procesar).

## Casos sin procesar (12-oct)

`CASOS_SIN_PROCESAR.xlsx` (fuera de git): 32 casos en 6 grupos, con lo que hay en Kobo y que hacer en cada uno, y una columna "Decision / notas" para ir llenando. Hallazgos nuevos:
- 526: en el Excel dice FRANCISCA ARROYO, pero en la hoja el usuario 526 es ERIKA ALEXANDRA CASIERRA (CS 101, F1-F4 completos, propietaria). Francisca es el 528 (caso "Otro").
- 685 Manuel Santos Cuero: su F1 quedo con usuario 690 y Casa 710; F2 y F3 si son 685/719. Procesable poniendo su documento (13056497) en la columna I.
- 744 Juan Quintero: F1 duplicado exacto; procesable eligiendo uno en la ventana.

### Decisiones caso por caso (12-oct)
- 744: procesar con el F1 del 30-sep (826857270); en la ventana elegir ese. Marca D borrada.
- 685: documento 13056497 en la columna I; marca D borrada (en la ventana el usuario 690 -> 685).
- 526: fila 40 = ERIKA ALEXANDRA CASIERRA (526, casa 101); FRANCISCA ARROYO agregada como 528 (fila 71).
- 433: procesar con Ronald Mauricio Prado (quien atendio). 471: procesar con Fanny Yuliana Quintero.
- 708: juego del 7-oct (cedula 59665249 confirmada con la foto); nombre LUZ MARIA DEL SOCORRO LANDAZURI QUIÑONES.
- **Regla "Otro" nueva:** ventana "Procesar / Saltar (Tiene otro)" cuando el F1 dice Otro. Marcas borradas de 624 y 480; agregados 320, 299, 304, 57 (filas 72-75).
- 763 (Paula, CS 521) y 864 (Felisa, Casa 593; verificar su documento 98528510) agregados (filas 76-77).
- Correcciones puntuales en Kobo (con ventana, script del 12-oct): F2 de 783 documento -> 1004636702 (las fotos de su cedula siguen siendo de Maria Lorena Caicedo); F4 de 459 usuario 452 -> 459 y documento -> 59688887; F4 826863709 -> MARIA ENID ARIAS JARAMILLO; F4 826867885 -> MARIA ZAIDA CORTES, CASA 125A; F4 829274695 -> CASA 521.
- Sin accion posible por ahora (falta trabajo de campo): 682 (falta F1), 824 y 528 (faltan F2 y F3), y los 11 no elegibles de El Triunfo.
- Quedan 27 pendientes para el bot.
- **Corrida 13:49:** resueltos y en TERMINADOS 744, 708, 685, 624 (Otro), 526 (Erika), 480 (Otro), 843 y 49. En 433 y 471 se eligio "Ninguno" en la ventana -> ahora tienen el registro decidido en la **columna O nueva "REGISTRO KOBO"** (ej. `F1=826845953`): el bot abre ese registro directo por la API, sin buscarlo ni preguntar; nombre final en L (Ronald / Fanny). Quedan 19 pendientes.

- Ventana de esquinas de la cedula: "Listo" habilitado desde el inicio. Sin puntos = "Listo (dejarla así)": se acepta la foto tal como esta (sube como -ajustada, no queda 'Revisar a mano' y no se vuelve a preguntar). Con 1-3 puntos se deshabilita; con 4 = "Listo (recortar)". Sin commit todavia.

- **Corrida 14:25:** completos 433 (Ronald), 471 (Fanny), 18, 75, 1 (Karyn), 247, 74, 459, 483, 498. A TERMINADOS: 74, 433, 459, 471, 483, 498.
  - Usuario 1: el bot le asigno el F4 de Jacinta (su otra casa 27B, mismo nombre, casa '27'). Arreglado: G = No encontrado, PDF del F4 sacado (respaldo en scratchpad) y PDF unido rehecho. **Regla nueva** (kobo.Coincidencia.confirmada + texto.documento_distinto): si la cedula del registro es claramente de otra persona y el usuario no coincide, no se acepta.
  - 75 y 247: en la ventana se eligio "Dejar lo de Kobo" y su F4 quedo con usuario 304 y 11 -> corregidos a 75 y 247 con correccion puntual.
  - 1 y 18: la hoja no se lleno (Google HTTP 429): la proxima corrida solo llena la hoja.
  - Pendientes: 505, 812, 528, 320, 299, 304, 57, 763, 864 (+ hoja de 1 y 18).

- **Vivienda inexistente / lote vacio (12-oct):** el bot lo detecta en el F1 por la API (condiciones especiales = vivienda inexistente, o "lote vacio"/"inexistente"/"inasistente" en Otro cual u observaciones; "aparente abandono" solo NO cuenta) y muestra una ventana. "Marcar RETIRADO": no se corrige ni se envia; Excel D = "Vivienda inexistente"; hoja F nombre, G 0, H direccion, I RETIRADO, J FOTOGRAFIA VIVIENDA, K KAREN QUIÑONES (como las RETIRADO que ya habia). Casos: 528 Francisca, 824 Ilda (marca 'Tiene otro' borrada). Hay ~40 F1 asi en Kobo.
- Arreglado: si el F4 ya tenia "No encontrado" y faltaba la hoja (18 y 1), el bot se detenia sin llenarla.

### Verificacion de lo ya cargado (12-oct, tarde)
- Ninguna de las 67 procesadas debia ser RETIRADO: todas con resultado "sin novedad", sin vivienda inexistente ni abandono; hoja 58 CONFIRMADO / 9 INCORPORADO.
- Nueva carpeta **`CONTINGENCIAL\TERMINADOS\LISTOS POR CARGAR`**: terminados sin errores aun no subidos al Drive (terminados.py ahora mueve ahi). `TERMINADOS\CARGADOS` = ya subidos (lo mueve el usuario).
- Hallazgos en CARGADOS (corregidos y pasados a LISTOS POR CARGAR para volver a subirlos):
  - **Oleisa Cuero:** en el Excel tenia usuario 782 (es 780); el bot lleno la fila 782 de la hoja (Johan G Aguirre Arboleda) con sus datos. Corregido: Excel 780, fila 780 llena, fila 782 vacia con I = PENDIENTE, carpeta/PDF '780_OLEISA CUERO'. **Proteccion nueva:** el bot no escribe una fila de la hoja si su nombre (B) o casa (E) no son de esa persona.
  - Firma del contratista cortada (ventana pequena): 711 F1 y F3, 75 F2; 761 F4 tenia la firma de campo. Rehechas.
  - No. Usuario de otra persona en Kobo: 761 F1 (762), 468 F4 (510), 562 F4 (572). Corregidos.

- Corrida 15:15: 824 y 528 RETIRADO (hoja verificada). 18 y 1: la hoja otra vez HTTP 429 de Google -> **arreglado:** leer la hoja reintenta con 429/5xx esperando 20, 40 y 60 s (sin commit todavia). Una segunda corrida lanzada a las 15:18 se cerro sola sin tocar nada (el navegador del bot estaba en uso).

- **Corrida 15:15 revisada:** 824 y 528 RETIRADO; 320, 299, 304, 57 (Otro), 763 y 864 completos -> LISTOS POR CARGAR. Corregido en Kobo: F4 de 320 (usuario 299 -> 320, documento de firma 36853120 -> 36835120); cedula de 763 (F1, F3: 5966480 y F4: 59666489 -> 59666480), tambien en Excel I y hoja G.
- **Columna L escrita en la hoja y P del Excel** para 17 ya procesados: FALLECIDO (656, 624, 553, 884, 687, 320, 299, 57), NUEVO PROPIETARIO (433, 633, 471, 859), 304 AUTORIZADA POR EL PROPIETARIO CON PODER, 480 FAMILIAR DEL PROPIETARIO, 1 POSEEDORA, 528/824 INVIABILIDAD VIVIENDA INEXISTENTE. Verificadas.
- revisar.py ahora toma la corrida que termino de ultima (antes tomo la que fallo al abrir).
- Solo quedan pendientes 18 y 1 (llenar la hoja; la proxima corrida ya reintenta el 429).
- Corrida 15:49 (18 y 1): la hoja se lleno, pero (a) la verificacion de 18 fallo porque la columna G muestra el documento con puntos ('13.015.205') y (b) la corrida de 1 se corto durante la espera del 429. Arreglado: el documento se compara por digitos y la espera usa wait_for_timeout. Filas 34 y 17 verificadas a mano y K = Si. **No quedan pendientes en el Excel**; 18 y 1 en LISTOS POR CARGAR. Raiz de CONTINGENCIAL vacia (solo POR CORREGIR y TERMINADOS).

- **POR CORREGIR / 783:** no hay otra foto de su cedula en Kobo (su F1 trae una factura de Cedenar a su nombre con CC 1004636702, que confirma el numero). Se pidio al equipo de campo tomar frente y reverso y reemplazarlas en el F2 _id 826845937 (instruccion en POR CORREGIR\LEEME.txt). Al tenerlas: borrar la marca E de 783 y correr main.py --limite 1.

## Lista de campo 2 (29 usuarios, 12-oct)
- Pasada a CANDIDATOS2.xlsx; resultado en USUARIOS_NUEVOS2.xlsx; los no procesados en CASOS_SIN_PROCESAR.xlsx (grupo 7).
- **Elegibles agregados a USUARIOS.xlsx (filas 78-80):** 288 YINER MANCILLA CORTES (117A; F3/F4 dicen usuario 161), 59 ANA LUCIA VIVEROS MONTAÑO (39), 87 ROSA ELENA GUAGUA SANCHEZ (28; su F2 tiene la cedula escrita como nombre).
- **Ya procesados por otro equipo (Dilia, CONFIRMADO):** 85 Ana Yanira Valverde, 323 Ana Ligia Quiñones -> no se procesan.
- **No elegibles:** 303 (la casa 106 es de Felisa Perseveranda, usuario 543), 349 (Angela Lorena Pai, falta F2, otro documento), 456 (es el usuario 356, ya RETIRADO; F1 nuevo con otro documento), 13 solo con F4, 8 sin formularios.

- Corrida 16:04 (288, 59, 87): completos. 87: el nombre del F2 quedo '59660419' (su cedula) porque la regla lo tomo como otra persona -> corregido en Kobo y regla arreglada (nombre sin letras = usar el del Excel). Revision "TODO BIEN"; los 3 en LISTOS POR CARGAR. Sin pendientes.

## Verificacion final (12-oct, noche)
- Script de verificacion completa (Kobo: registro, usuario, nombre, documento, casa, firma del bot; hoja F-L; PDF unido; carpeta) sobre las 79 personas de USUARIOS.xlsx. Resultado: **75 TERMINADO OK**, 2 RETIRADO OK (824, 528), 1 POR CORREGIR (783, fotos de cedula), 1 NO PROCESADO (682, falta F1). Reporte en **REPORTE_FINAL.xlsx** (116 personas con las listas de campo).
- Corregido en esta verificacion: documentos mal digitados en Kobo (761 F1 tambien Excel I y hoja G, 873 F2, 654 F4, 645 F2, 711 F2, 843 F2/F4, 304 F2/F4) y firma de campo en el F4 de 299 (el bot no pudo borrarla: "No habia firma para borrar"). Las 8 carpetas pasaron de CARGADOS a LISTOS POR CARGAR para volver a subirlas.
- Columna L: N/A en las 61 filas CONFIRMADO de KAREN QUIÑONES sin nada que explicar (verificado). El bot ahora pone N/A solo en esos casos.
- El bot ahora comprueba despues de enviar que la firma que quedo en Kobo sea la suya; si no, "Revisar a mano".
- Carpetas: CARGADOS 66, LISTOS POR CARGAR 9, POR CORREGIR 1.

## La hoja de Google como tercera fuente para buscar (12-oct)
- Al empezar la corrida se compara cada usuario pendiente del Excel con su fila de la hoja: nombre inicial (B) parecido o la misma casa (E). Si no cuadra, sale una ventana que propone el número de la hoja que sí parece suyo ("Usar este número" cambia la columna B del Excel; "Dejar el del Excel" no cambia nada). Con PREGUNTAR_DUDAS=0 solo avisa y no usa los datos de esa fila.
- En Kobo se busca y se compara también con el nombre inicial de la hoja (2 términos de búsqueda más como máximo).
- Sector: si el barrio del registro en Kobo es de otro sector que la dirección de la hoja (LIBERTAD, TRIUNFO, BRISAS, UNION VICTORIA), la casa no cuenta para confirmarlo y aparece "OTRO SECTOR".
- Prueba de solo lectura: los 79 del Excel actual cuadran con la hoja. Simulando a Oleisa con el 782, el bot propone el 780 (nombre 100 %, misma casa).

## Revision de coherencia con las cedulas (12-oct, noche)
- Se revisaron las 75 carpetas de TERMINADOS: cedula leida a ojo (DOCUMENTO.pdf) contra Excel, hoja, Kobo (4 formularios), PDF de la carpeta e historial de Kobo. Resultado en `REPORTE_TERMINADOS.xlsx` (pestanas Resumen y Problemas).
- Los 75 numeros de cedula coinciden con el Excel (I), la hoja (G) y el documento principal de Kobo.
- Corregido en Kobo (verificado por la API, PDF regenerados):
  - Documento de la firma mal escrito: 64, 74, 468, 471, 483, 498, 562, 581, 595, 780.
  - Nombres mal escritos segun la cedula (Excel A, Kobo, hoja F y nombre de la carpeta): 49 JOHN, 498 DIOLINDA BELALCAZAR, 512 PORTOCARRERO, 535 LEIDY, 536 YOMAIRA, 553 ALEXANDRA, 562 ERIBERTA ARROLLO, 595 MONTAÑO, 623 CINDY ... QUIÑONES, 873 QUIÑONES.
  - Los nombres incompletos (falta un apellido) y los sin Ñ se dejan asi (decision del usuario).
- Esas 17 carpetas quedaron en LISTOS POR CARGAR: hay que volver a subirlas al Drive. 10 cambiaron de nombre (borrar la vieja en el Drive): 49_JHON..., 498_BIOLINDA BELARCAZAR, 512_..PORTOCARRENO, 535_LEYDY.., 536_YAMAIRA.., 553_..ALEJANDRA.., 562_ERIBERTO ARROYO.., 595_..MOTAÑO.., 623_CINDI..QUINONES, 873_..QUINONEZ.
- La cuenta de Kobo (pronetumaco08) la usan otras personas: el historial muestra ediciones desde varias IP. Este PC es 181.32.255.247. La IP 181.62.56.15 edito el 711 despues de nosotros (cambio firmas y nombre, y se perdio el soporte de propiedad del F1).
- Decidido despues:
  - 633: cara de la cedula enderezada (esquinas marcadas en la ventana), DOCUMENTO.pdf y F2 rehechos -> LISTOS POR CARGAR.
  - 708 y 864 -> POR CORREGIR con pedido a campo en el LEEME (708: foto de la cara; 864: cedula y numero correcto).
  - 711: firma del bot otra vez en los 4 formularios; Excel A = CLARA LANDAZURI DE CASTILLO (como la cedula, Kobo y hoja); carpeta en POR CORREGIR hasta recuperar la foto del soporte de propiedad (PDF viejo del Drive o campo) y subirla al F1 _id 829150879.
  - 57: se deja como esta. 744: nada que hacer (el duplicado de Kobo no es nuestro).
- Carpetas al cierre: CARGADOS 54, LISTOS POR CARGAR 18 (las 17 corregidas + 633), POR CORREGIR 4 (783, 708, 864, 711).

## Formato de los PDF (12-oct, noche)
- Pedido: imprimir como lo hace la persona: boton de impresora del formulario > Modo carta > Modo retrato > PREPARAR; y en Ctrl+P: carta, SIN encabezado y pie de pagina, SIN graficos de fondo.
- El bot ya lo hace siempre (pdf.preparar_impresion + PDF_ENCABEZADOS=0 por defecto).
- Se volvieron a imprimir TODOS los PDF entregados sin enviar nada a Kobo (abrir, preparar, imprimir, cerrar). Las 72 carpetas de CARGADOS quedaron en LISTOS POR CARGAR para volver a subirlas.
- Firmas del contratista (Adriana F1-F3, Jhon F4): se probo un trazo mas grueso y el usuario pidio volver a la firma de siempre. Quedo la de siempre. Al borrar, el bot no veia la firma guardada (Kobo la pinta ~2 s despues y la marca en un input con data-loaded-file-name): ahora espera a que aparezca, comprueba que el lienzo quedo vacio y, despues de firmar, que el lienzo tenga solo la firma del bot (si no, la borra y repite; si sigue mal no firma).
- Revision final (solo lectura): 274 de 274 registros con la firma del contratista bien. Se corrigieron los 5 que dano la prueba (18 F1 con dos firmas encimadas; 57 F1-F4 con el trazo grueso).

## Procesamiento aparte (12-oct, noche)
- Pedido: usuarios procesados por aparte, SIN escribir en la hoja de Google; lo de la hoja va a un Excel local con sus mismas columnas y RESPONSABLE (K) en blanco; la cedula y la factura que entrega el usuario reemplazan lo que tenga Kobo.
- Se corre con `.venv\Scripts\python aparte.py` (mismo bot, otros archivos): USUARIOS_APARTE.xlsx, HOJA_APARTE.xlsx (A-E e I copiadas de la hoja de Google al agregar al usuario), ENTRADA_APARTE\<usuario>\ (CEDULA_CARA.jpg, CEDULA_REVERSO.jpg, FACTURA.jpg), carpetas en CONTINGENCIAL_APARTE\, casos en CASOS_APARTE.xlsx y registros en salida_aparte\.
- Usuarios agregados: 733 ELSI DOLORES QUIÑONES SEVILLANO (nombre de la cedula 27.499.669; en la hoja 'ELSY QUINONES', fila 749), casa 452. Kobo: F1 826430867 (su soporte era una foto de la fachada), F2 826430871 (cara de la cedula girada; reverso bien), F3 826430872, sin F4. Se entrego cara de la cedula y factura Cedenar (no el reverso).
- 785 SONIA FELISA CARVAJAL RODRIGUEZ (cedula 1.086.724.371), casa 442; hoja fila 801. Kobo: F1 826430907, F2 826430915, F3 826431059, sin F4. Entrego cara, reverso y factura.
- 752 YESENIA ORTIZ AGUIÑO (cedula 1.089.001.411), casa SIN NUMERO ("DIV 1" en hoja, Kobo y factura); hoja fila 768. Kobo: F1 826430894, F2 826430898, F3 826430901, sin F4 (anotados en la columna O porque en Kobo otra persona tambien tiene el usuario 752: Wilman Marquias Jimenez Valencia, doc 98010006, casa 871). Entrego cara, reverso y factura.
- 784 SANDRA PATRICIA CUERO PRADO (cedula 59.676.551), casa 494; hoja fila 800 ('SANDRA PATRICIA CUERO'). Kobo: F1 826848059, F2 826848060, F3 826848067, F4 829274468 (dice Casa 490; el Excel y la hoja dicen 494). Anotados en la columna O porque otro F4 usa el usuario 784: Dely Daliana Mojarrango Ayala, Brisas de los Angeles casa 137A. Entrego cara, reverso y factura.
- 731 IBIS MARIA ARBOLEDA BALTAN (cedula 1.087.108.806), casa 498; hoja fila 747 ('IBIS ARBOLEDA'). Kobo: F1 826848085 (dice Casa 494), F2 826848113, F3 826848116, sin F4 (columna O). Entrego cara, reverso y factura.
- 774 ANA LILIANA CORREA RODRIGUEZ (cedula 59.684.123), casa 496; hoja fila 790 ('LILIANA CORREA'). Kobo: F1 826848125, F2 826848127, F3 826848129, sin F4 (columna O). OJO: en la misma casa 496 y usuario 774 hay otros registros de LUZ INES BOLAÑOS (doc 36910078): F1 826430874, F2 826430882, F3 826430888. La factura dice LILIANA CORREA pero con cedula 1087421326 (no es la suya). FALTAN sus fotos (cedula y factura) en ENTRADA_APARTE\774: no llegaron como archivo.
- 750 JULLYS COHINTA WISAMANO LARA (cedula 59.671.130, vista en Kobo), casa 544; hoja fila 766. Kobo: F1 829154193, F2 829154209, F3 829154219, F4 829274680 (este dice usuario 759; columna O). Solo entrego factura (Cedenar feb-2021, a su nombre); la cedula se deja la de Kobo (el bot la recorta).
- 723 YIMY WISAMANO LARA (cedula 12.918.068), casa 546; hoja fila 739. Kobo: F1 829154248, F2 829154271, F3 829154285, F4 829274717 (columna O; su hermana Paula Yolima aparece al buscar por nombre). Entrego cara, reverso y factura.
- 844 LEONARDO FABIO AVILA GUEVARA (cedula 13.057.174), casa 601; hoja fila 860. Kobo: F1 829154460, F2 829154520, F3 829154533, sin F4 (columna O). Entrego cara, reverso y factura.
- 860 NANCY MILENA GARCIAS CORTES (cedula 59.672.593: dice GARCIAS; factura y hoja dicen GARCIA), casa 639 (el usuario escribio 'Casa 860' por error); hoja fila 876. Kobo: F1 829154592 ('Gracias'), F2 829154665 (documento 59672592: le falta corregir el ultimo digito), F3 829154684, sin F4 (columna O). FALTAN sus fotos en ENTRADA_APARTE\860.
- PROCESADOS (12-oct, noche) con `aparte.py --usuarios 733,785,752,784,731,750,723,844`: los 8 completos, carpetas en CONTINGENCIAL_APARTE (unido 26-34 pag), filas en HOJA_APARTE.xlsx con K en blanco. Sin F4 en Kobo: 733, 785, 752, 731, 844. Revision de coherencia (REPORTE_APARTE.xlsx): todo bien; se corrigio el documento de la firma del F4 del 723 (12918066 -> 12918068). Pendientes 774 y 860: faltan sus fotos.
- Al terminar de procesar los aparte: revisar coherencia de documentos (el bot no corrige el documento del F2 ni el de las firmas; ej. 860 F2).
- Para agregar mas: `.venv\Scripts\python herramientas\agregar_aparte.py --usuario N --casa N --nombre "..." --documento N --cara X --reverso Y --factura Z` (lee la hoja y Kobo sin escribir en ellos).

## Pendientes (al 12-oct, noche)

### 1. Subir al Drive (lo hace el usuario)
- Las 72 carpetas de `CONTINGENCIAL\TERMINADOS\LISTOS POR CARGAR` (todas se reimprimieron en formato carta): reemplazar las del Drive. En 10 cambio el nombre de la carpeta (49, 498, 512, 535, 536, 553, 562, 595, 623, 873): borrar la vieja del Drive.
- Las 10 carpetas de `CONTINGENCIAL_APARTE` (procesamiento aparte, sin la hoja de Google). Sus datos de hoja estan en `HOJA_APARTE.xlsx` (K en blanco).

### 2. Esperando a campo (`CONTINGENCIAL\POR CORREGIR`, instrucciones en su LEEME.txt)
- 783 Maria Lorena Arboleda Reina: fotos de su cedula (el F2 tiene la de otra persona).
- 708 Luz Maria del Socorro Landazuri: foto de la cara de la cedula (la de Kobo es otra foto).
- 864 Felisa Cecilia Quiñones (casa 593): cedula y numero correcto (98528510 no es el de Felisa, 59667399).
- 711 Clara Landazuri de Castillo: foto del soporte de propiedad que se borro en Kobo (PDF viejo del Drive o campo); coordinar con quien edito desde la IP 181.62.56.15.

### 3. Para avisar al equipo (no se tocan)
- Busqueda SOLO por cedula de lo que falta (REPORTE_BUSQUEDA_CEDULA.xlsx, 12-oct noche):
  - F4 que faltan (35: 28 de USUARIOS.xlsx y 7 aparte): ninguno existe en Kobo con su cedula ni con un numero casi igual (los 3 casi iguales son otras personas en otras casas). El acta del F4 no se hizo.
  - 682 JOHNY ADAN CABEZA: cedula 1010028491 (sacada de su F2). Tiene F2 829157669 y F3 829151894 (usuario 682, casa 669), pero NO F1 ni F4 con esa cedula: falta la visita del F1 (el bot empieza por el F1).
  - 824 y 528 (RETIRADO): documento '00000000', no hay cedula que buscar; F2 y F3 no aplican por ser lote vacio.
- Otras personas con un numero de usuario ajeno en Kobo (son otros usuarios de la hoja):
  - Wilman Marquias Jimenez Valencia (98010006, casa 871): en la hoja es el 572, en Kobo tenia 752. CORREGIDO el 12-oct (solo esos campos, verificado por la API): F1 829156230, F2 829156339 y F3 829156380 con usuario 572; nombre del F3 ('Wilman Geovanni Ulloa Quiñones') y de su firma ('...Valenciana') -> 'Wilman Marquias Jiménez Valencia'.
  - Dely Daliana Mojarrango Ayala (1151450384, Brisas casa 137A): es el 748. CORREGIDO su F2 829157190 (usuario vacio -> 748). Su F4 829789905 no se podia guardar por Enketo (le faltan fotos obligatorias de fachada, medidor, area exterior e interior y la firma del contratista): el usuario se corrigio 784 -> 748 con la edicion masiva de la API de Kobo (PATCH /api/v2/assets/<uid>/data/bulk/, con el csrftoken de la sesion), que cambia solo ese dato sin validar el formulario; se conservaron sus 5 adjuntos. Las fotos y la firma que le faltan siguen pendientes de campo.
  - Luz Ines Bolaños (36910078): no esta en la hoja; registrada con el 774 en la casa 496 de Liliana Correa.
  - 864: el 98528510 solo aparece en sus propios registros (casa 593); la cedula de Felisa es 59667399 (843, casa 596). En la hoja la casa 593 A B es de ANGELA MARIA VALLECILLA (883).
- 744: F1 duplicado sin procesar 826426100.
- 87: su F1 no tiene la firma del usuario en Kobo.
- 682: no procesado (no tiene formulario 1 en Kobo).
- 57: F4 a nombre de la madre fallecida con datos internos distintos (se deja asi por decision del usuario).

## Como seguir (con el Excel cerrado y el Chrome de la hoja abierto)

1. Abrir el Chrome de la hoja: `herramientas\abrir_chrome_hoja.ps1`.
2. Ejecutar lo que toque:
   - Bot: `.venv\Scripts\python main.py --limite 10`.
   - Revisar el lote: `.venv\Scripts\python herramientas\revisar.py`.
   - Corregir con ventanas: `.venv\Scripts\python herramientas\corregir.py`.
   - Soportes de la hoja: `.venv\Scripts\python herramientas\soportes.py`.
   - Mover terminadas: `.venv\Scripts\python herramientas\terminados.py --mover`.
