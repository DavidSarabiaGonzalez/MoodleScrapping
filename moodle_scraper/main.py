"""Orquestador CLI.

Modos:
  python -m moodle_scraper.main --from-fixture ./fixtures_html/tarea_ide_java.html
      -> prueba offline: parsea, crea carpetas en ./salida, guarda feedback/descripción e informe.

  python -m moodle_scraper.main --live
      -> abre Chromium, login MANUAL, recorre cursos->tareas y descarga todo.
"""
from __future__ import annotations

import argparse
import glob
import logging
import os
import time

from . import config
from .auth import cookies_header, login_manual
from .courses import list_assigns_in_course, list_courses, save_debug
from .downloader import download_url, polite_pause
from .log import setup_log
from .naming import build_filename, grade_percent, normalize_grade, sanitize_component, snake_case, unique_path
from .parse_assign import parse_assignment_html
from .report import save_report
from .storage import default_output, load_aliases, pretty_course, task_dir


def process_task(data: dict, output: str, aliases: dict,
                 cookie_hdr: str = "", download: bool = True,
                 log: logging.Logger | None = None,
                 prefix: str = "",
                 course_hint: dict | None = None,
                 section_hint: str = "") -> tuple[dict, list[dict]]:
    # El curso que estamos recorriendo manda (siempre fiable); lo parseado vale
    # de respaldo (p. ej. modo fixture, donde no hay navegación).
    short = ((course_hint or {}).get("short") or data.get("course_short") or "")
    title = ((course_hint or {}).get("title") or data.get("course_title") or "")
    course = pretty_course(short, title, aliases)
    section = data.get("section") or section_hint or ""
    tdir = task_dir(output, course, section or "tema", data["task_name"])
    grade_raw = data.get("grade_raw")
    errors: list[dict] = []
    saved: list[dict] = []
    n_files = len(data.get("files", []))
    if log:
        log.info(f"{prefix}📄 {data['task_name']}  [nota: {grade_raw or 'Sin nota'}] "
                 f"({n_files} archivos, feedback={'sí' if data.get('feedback') else 'no'})")

    # 1) feedback del profe como hermano
    if data.get("feedback"):
        fb_name = sanitize_component(snake_case(data["task_name"])[:60] + "_feedback") + ".txt"
        with open(os.path.join(tdir, fb_name), "w", encoding="utf-8") as f:
            f.write(f"Tarea: {data['task_name']}\nNota: {grade_raw or 'Sin nota'}\n\n{data['feedback']}\n")
        saved.append({"original": "feedback_profesor", "final": fb_name, "tipo": "feedback"})
        if log:
            log.info(f"{prefix}  + feedback guardado: {fb_name}")

    # 2) descripción/enunciado textual
    if data.get("description"):
        with open(os.path.join(tdir, "descripcion.txt"), "w", encoding="utf-8") as f:
            f.write(data["description"] + "\n")

    # 3) texto en línea + enlaces
    if data.get("online_text") or data.get("online_links"):
        on_name = sanitize_component(snake_case(data["task_name"])[:60] + "_online") + ".txt"
        with open(os.path.join(tdir, on_name), "w", encoding="utf-8") as f:
            f.write((data.get("online_text") or "") + "\n\nEnlaces:\n")
            for u in data.get("online_links", []):
                f.write(u + "\n")
        saved.append({"original": "texto_en_linea", "final": on_name, "tipo": "online"})
        if log:
            log.info(f"{prefix}  + texto online guardado: {on_name}")

    # 4) archivos (entregas + enunciados + adjuntos feedback)
    for j, fi in enumerate(data.get("files", []), 1):
        final = build_filename(fi["filename"], grade_raw)
        dest = os.path.join(tdir, final)
        if os.path.exists(dest):
            # existe: unique_path decide si hay colisión real
            dest = unique_path(tdir, final,
                               extra=f"{course[:20]}_{normalize_grade(grade_raw)[:15]}")
            if dest.endswith(final) and os.path.exists(dest):
                pass  # download_url hará skip por tamaño
        if log:
            log.info(f"{prefix}  [{j}/{n_files}] {fi['kind']}: {fi['filename']} -> {os.path.basename(dest)}")
        if download and cookie_hdr:
            polite_pause()
            ok, motivo = download_url(fi["url"], dest, cookies=cookie_hdr,
                                      log=log, label=os.path.basename(dest))
            if not ok:
                errors.append({"curso": course, "tarea": data["task_name"],
                               "archivo": fi["filename"], "motivo": motivo, "url": fi["url"]})
                if log:
                    log.error(f"{prefix}    ERROR descarga: {fi['filename']} :: {motivo}")
                continue
            if motivo == "ya_existe_mismo_tamano" and os.path.basename(dest) != final:
                pass
        saved.append({"original": fi["filename"], "final": os.path.basename(dest),
                      "tipo": fi["kind"]})

    entry = {"curso": course, "tema": section,
             "tarea": data.get("task_name", ""), "nota": grade_raw or "Sin nota",
             "nota_pct": grade_percent(grade_raw),
             "archivos": saved, "carpeta": os.path.relpath(tdir, output)}
    return entry, errors


def run_fixture(path: str, output: str, log: logging.Logger | None = None) -> None:
    aliases = load_aliases()
    log = log or setup_log(output)
    log.info(f"Modo fixture (offline, sin descargar): {path}")
    with open(path, encoding="utf-8", errors="ignore") as f:
        html = f.read()
    data = parse_assignment_html(html, url="https://aulavirtual.murciaeduca.es/mod/assign/view.php?id=696472")
    entry, _ = process_task(data, output, aliases, download=False, log=log)
    # en fixture marcamos archivos como pendientes de descarga real
    save_report([entry], [], output)
    log.info(f"OK fixture -> {entry['carpeta']} | nota={entry['nota']} | archivos={len(entry['archivos'])}")


def run_live(output: str, log: logging.Logger | None = None, verbose: bool = False,
             base_url: str = "") -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Falta playwright. Activa .venv e instala: .venv/bin/python -m pip install -r requirements.txt && .venv/bin/python -m playwright install chromium")
        raise SystemExit(1)
    log = log or setup_log(output, verbose)
    base = (base_url or "").strip().rstrip("/") or config.BASE_URL
    t0 = time.time()
    aliases = load_aliases()
    entries, errors = [], []
    empty_courses: list[str] = []
    debug_dir = os.path.join(output, "_debug")
    n_files_ok = n_files_skip = n_files_err = 0
    with sync_playwright() as p:
        log.info(f"Abriendo Chromium ({base}): loguéate MANUALMENTE en la ventana.")
        try:
            browser, context, page = login_manual(p, base, log=log)
        except TimeoutError as e:
            log.error(str(e))
            return
        try:
            log.info("Sesión detectada. Listando tus cursos...")
            courses = list_courses(page, base, log=log)
            log.info(f"Cursos encontrados: {len(courses)}")
            for ci, c in enumerate(courses, 1):
                hint = {"short": c["short"], "title": c.get("title", "")}
                course_folder = pretty_course(hint["short"], hint["title"], aliases)
                os.makedirs(os.path.join(output, course_folder), exist_ok=True)
                log.info(f"\n━━ Curso [{ci}/{len(courses)}]: {c['short']} ({c['url']})")
                log.info(f"   Carpeta: {os.path.join(output, course_folder)}")
                assigns = list_assigns_in_course(
                    page, c["url"], log=log, debug_dir=debug_dir,
                    course_label=f"{c['id']}_{course_folder}")
                log.info(f"   Tareas encontradas: {len(assigns)}")
                if not assigns:
                    empty_courses.append(f"{c['short']} ({c['url']})")
                for ai, a in enumerate(assigns, 1):
                    prefix = f"   [{ai}/{len(assigns)}] "
                    try:
                        log.info(f"{prefix}→ {a.get('text') or a['href']}")
                        page.goto(a["href"], wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1200)
                        # sesión caducada?
                        if "login/index.php" in (page.url or ""):
                            log.warning("   !! Sesión caducada. Vuelve a loguearte en la ventana y pulsa ENTER aquí.")
                            input("   ENTER para continuar... ")
                            page.goto(a["href"], wait_until="domcontentloaded", timeout=60000)
                        html = page.content()
                        data = parse_assignment_html(html, url=a["href"])
                        if not data.get("course_short") and not data.get("course_title"):
                            log.warning(f"{prefix}breadcrumb sin curso: uso el curso en navegación "
                                        f"({c['short']}). Guardo HTML para revisar.")
                            try:
                                save_debug(html, debug_dir, f"tarea_{data.get('task_id') or ai}_{course_folder}", log)
                            except Exception:
                                pass
                        entry, errs = process_task(
                            data, output, aliases,
                            cookie_hdr=cookies_header(context), download=True,
                            log=log, prefix=prefix,
                            course_hint=hint, section_hint=a.get("section", ""))
                        entries.append(entry)
                        errors.extend(errs)
                        for s in entry["archivos"]:
                            if s["tipo"] in ("entrega", "enunciado", "retroalimentacion_adjunto", "otro"):
                                n_files_ok += 1
                        n_files_err += len(errs)
                        log.info(f"{prefix}✓ {data['task_name']} [{entry['nota']}] "
                                 f"({len(entry['archivos'])} ficheros, {len(errs)} errores)")
                    except Exception as e:  # seguir con el resto
                        errors.append({"curso": c["short"], "tarea": a.get("text", a["href"]),
                                       "archivo": "-", "motivo": f"{type(e).__name__}: {e}", "url": a["href"]})
                        log.error(f"{prefix}✗ ERROR {a['href']}: {e}")
        finally:
            save_report(entries, errors, output)
            dt = time.time() - t0
            log.info(f"\nTerminado en {dt / 60:.1f} min: "
                     f"{len(entries)} tareas, {n_files_ok} archivos, {n_files_err} errores.")
            if empty_courses:
                log.warning(f"Cursos sin tareas detectadas ({len(empty_courses)}):")
                for ec in empty_courses:
                    log.warning(f"  - {ec}")
                log.warning("Si alguno debería tener tareas, revisa salida/_debug/ o ábrelo "
                            "manualmente: quizá usa otro formato de curso o no tiene Tareas assign.")
            log.info(f"Informe en {output}/index.html y resumen.json. "
                     f"Detalle en {output}/backup.log. Errores: {len(errors)}")
            if errors:
                log.warning("Hay errores: revísalos en errores_para_manual.txt para descarga manual.")
            browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Backup personal Aula Virtual MurciaEduca")
    ap.add_argument("--from-fixture", help="HTML local de tarea para prueba offline")
    ap.add_argument("--live", action="store_true", help="Recorrido real con login manual")
    ap.add_argument("--all-fixtures", action="store_true", help="Procesa todos los HTML de fixtures_html/")
    ap.add_argument("--regen", action="store_true",
                    help="Regenera solo index.html desde resumen.json (sin descargar nada)")
    ap.add_argument("-o", "--output", default=config.OUTPUT_DIR)
    ap.add_argument("--url", default="",
                    help="URL del Aula Virtual (por defecto la de MurciaEduca)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Muestra pausas, reintentos y detalle extra (siempre queda en backup.log)")
    args = ap.parse_args()
    output = args.output
    os.makedirs(output, exist_ok=True)
    log = setup_log(output, verbose=args.verbose)
    if args.regen:
        from .report import regen_index
        try:
            n_tareas, n_err = regen_index(output)
        except FileNotFoundError:
            log.error(f"No existe {os.path.join(output, 'resumen.json')}: nada que regenerar.")
            return
        log.info(f"index.html regenerado desde resumen.json: {n_tareas} tareas, {n_err} errores. "
                 f"Sin descargar nada.")
        return
    if args.all_fixtures or (not args.live and not args.from_fixture):
        paths = sorted(glob.glob(os.path.join(config.FIXTURES_DIR, "*.html")))
        if not paths:
            log.info(f"No hay fixtures en {config.FIXTURES_DIR}/. Usa --live para descarga real.")
            return
        log.info(f"Modo fixtures offline: {len(paths)} HTML (sin descargar PDFs reales)")
        aliases = load_aliases()
        entries = []
        for i, path in enumerate(paths, 1):
            log.info(f"[{i}/{len(paths)}] {os.path.basename(path)}...")
            with open(path, encoding="utf-8", errors="ignore") as f:
                data = parse_assignment_html(f.read(), url="")
            e, _ = process_task(data, output, aliases, download=False, log=log,
                                prefix=f"[{i}/{len(paths)}] ")
            entries.append(e)
            log.info(f"[{i}/{len(paths)}] ✓ -> {e['carpeta']}")
        save_report(entries, [], output)
        log.info(f"Hecho: {len(entries)} tareas. Informe en {output}/index.html")
    elif args.from_fixture:
        run_fixture(args.from_fixture, output, log)
    elif args.live:
        run_live(output, log, verbose=args.verbose, base_url=args.url)


if __name__ == "__main__":
    main()
