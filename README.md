# Backup personal Aula Virtual MurciaEduca

Programa personal para descargar tus entregas de Tareas Moodle con su nota en el nombre.
Auth siempre **manual** (sin contraseña en código).

## Estructura

```
moodle_scraper/
  config.py      # URLs, reintentos, etiquetas en español
  auth.py        # login manual con Playwright (Chromium propio)
  courses.py     # Mis cursos -> tareas assign
  parse_assign.py# parser tolerante (no asume Moodle estándar)
  naming.py      # snake_case + [nota] válido Windows/Linux
  storage.py     # ./salida/<curso>/<tema>/<tarea>/ + aliases.json
  downloader.py  # reintentos x3, pausas, dedup por tamaño
  report.py      # resumen.json + index.html + errores_para_manual.txt
  main.py        # CLI
aliases.json       # genérico (vacío): aquí NO pongas nombres reales
aliases.local.json # solo en tu máquina (ignorado por git): tus nombres cortos, ej. "Despliegue de aplicaciones web" -> "despliegue"
fixtures_html/     # aquí guardas HTML de ejemplo (Ctrl+S, solo HTML)
salida/            # resultado
```

Salida por tarea:
```
./salida/programacion/ut02_introduccion_al_lenguaje_java/tarea_1_evaluacion_de_un_ide_para_java/
  trabajo_programacion_ide [7,00_10,00].pdf   # entrega con nota
  tarea1_evaluacion_ides [7,00_10,00].pdf     # enunciado del profe, misma nota
  tarea_1_..._feedback.txt                    # comentarios retroalimentación
  descripcion.txt / *_online.txt              # cuando hay texto/enlaces
```

## Sin Python instalado: doble clic (Windows y Linux)

**Windows:** doble clic en **`AulaVirtual.bat`** · **Linux:** doble clic o `./aula-virtual.sh` en terminal.

Sin ventana de consola: usan tu **Brave** del sistema si lo tienes (evitan 650 MB de
descarga); si no, descargan Chromium solo una vez. La primera vez crean `.venv`
e instalan dependencias solos. Luego abren la interfaz en tu navegador.

## Interfaz web (también sin instalador)

```bash
.venv/bin/python -m moodle_scraper.gui
```

Abre una página local con el mismo estilo del informe:

- Campo con la dirección de tu Aula Virtual (ej. `https://moodle.com`).
- **⬇ Iniciar copia de seguridad**: abre el navegador para login manual y muestra
  el progreso y el registro en vivo aquí mismo.
- **🔄 Regenerar página HTML**: rehace el informe sin descargar nada.
- **📄 Abrir informe**: muestra tu `salida/index.html` con sus archivos.

## Uso por terminal (alternativa)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

## Probar sin tocar el servidor (offline)

```bash
.venv/bin/python -m moodle_scraper.main --from-fixture fixtures_html/tarea_ide_java.html -o salida
# o todos: .venv/bin/python -m moodle_scraper.main --all-fixtures -o salida
# abre salida/index.html para ver el overall
```

Regenerar solo la página (sin descargar nada, usa `resumen.json` tal cual):

```bash
.venv/bin/python -m moodle_scraper.main --regen -o salida
```

## La página informe (index.html)

Un solo archivo autocontenido (sin internet, se abre con doble clic):

- Tema **automático** (claro/oscuro según tu sistema) con botón 🌓 para forzarlo.
- Tarjetas: tareas, archivos, cursos, con nota y **media global en %**
  (normaliza tus escalas 0–10 y 0–100; “Sin nota” no entra en medias).
- Tabla **por curso** con tareas, archivos y media.
- **Buscador** (tarea/tema/curso/archivo), **filtro por curso** y
  **orden** pinchando cabeceras (la nota ordena por % y deja “Sin nota” al final).
- Cada archivo **enlaza a tu copia local** (`salida/...`), con icono por tipo
  (📄 entrega, 📝 enunciado, 💬 feedback…) y la nota con barrrita de %.
- Sección de **errores para descarga manual**.

## Feedback de progreso (para saber que está vivo)

En consola verás siempre, con hora:

```
━━ Curso [1/6]: programacion (...)
   Tareas encontradas: 8
   [1/8] → Tarea 1. Evaluación de un IDE...
   [1/8] 📄 Tarea 1... [nota: 7,00 / 10,00] (2 archivos, feedback=sí)
   [1/8]   [1/2] entrega: Trabajo...pdf -> trabajo... [7,00_10,00].pdf
    ⬇ trabajo...pdf: 42% (256.0 KB/600.0 KB)
    ✓ trabajo...pdf: descargado (600.0 KB)
    ＝ otro.pdf: ya existe (1.2 MB), se salta
    ↻ reintento 2/3 / ✗ ERROR descarga ... (sigue con el resto)
Terminado en 3.2 min: 24 tareas, 51 archivos, 2 errores.
```

Todo queda además en `salida/backup.log` (detalle completo aunque no uses `-v`).
Para depurar pausas/reintentos: añade `-v` (`--verbose`).

```bash
.venv/bin/python -m moodle_scraper.main --live -o salida -v
```

## Descarga real (con pausas anti-baneo)

```bash
.venv/bin/python -m moodle_scraper.main --live -o salida
# 1. se abre Chromium -> loguéate MANUALMENTE
# 2. pulsa ENTER en la terminal
# 3. recorre cursos->tareas, 1 descarga a la vez, 3 reintentos, sigue ante errores
# 4. al final: salida/resumen.json + index.html + errores_para_manual.txt
```

## Notas

- Cursos: incluye todos. El programa autodetecta el nombre de carpeta (limpia el
  prefijo del profesor y pasa a snake_case); si quieres nombres cortos
  (`programacion`, `dwes`…), ponlos en `aliases.local.json`
  (solo local, ignorado por git; `aliases.json` queda genérico). La carpeta del
  curso se crea siempre, aunque no tenga tareas.
- Si un curso da 0 tareas, el programa visita también sus páginas de sección
  (formato "una sección por página") y, si sigue sin haber, lo avisa al final y
  guarda `salida/_debug/curso_*.html` para revisarlo manualmente.
- Duplicados: por tamaño (si existe con mismo tamaño, se salta; si cambia la nota, se renombra).
- Sin nota: `nombre [Sin nota].ext`. Escala tal cual Moodle (`7,00_10,00`, `82_100`).
- Si una tarea falla (red/404/sesión), se apunta en `errores_para_manual.txt` para descarga manual.
