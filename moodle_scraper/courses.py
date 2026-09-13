"""Navegación Moodle: Mis cursos -> secciones -> tareas assign.

Robusto ante formatos de curso distintos (todo en una página o una sección
por página) y ante carga diferida de contenidos por JS.
"""
from __future__ import annotations

import logging
import os
import re

#: Por cada enlace a una tarea, intenta heredar el nombre de la sección que lo
#: contiene (sirve de fallback si el breadcrumb de la página de la tarea falla).
_ASSIGN_JS = """els => els.map(e => {
  const href = e.href.split('#')[0];
  const text = (e.innerText || '').trim();
  let sec = '';
  const box = e.closest('li.section, li[id^="section-"], [data-sectionid], .course-section, .section, .contentnomorelink');
  if (box) {
    const t = box.querySelector('.sectionname, .section-title, h3.sectionname, .section_title, .sectionname a');
    if (t) sec = (t.innerText || '').trim();
  }
  return {href: href, text: text, section: sec};
})"""


def list_courses(page, base_url: str, log: logging.Logger | None = None) -> list[dict]:
    page.goto(f"{base_url}/my/courses.php", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("a[href*='course/view.php?id=']", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    links = page.eval_on_selector_all(
        "a[href*='course/view.php?id=']",
        "els => els.map(e => ({href: e.href, text: e.innerText.trim(), title: e.title || ''}))",
    )
    seen, out = set(), []
    for l in links:
        m = re.search(r"id=(\d+)", l["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        if l["text"]:
            out.append({"id": m.group(1), "short": l["text"], "title": l["title"],
                        "url": f"{base_url}/course/view.php?id={m.group(1)}"})
    if log:
        log.info(f"Página Mis cursos cargada: {len(out)} cursos.")
    return out


def _collect_assigns(page) -> list[dict]:
    try:
        items = page.eval_on_selector_all("a[href*='mod/assign/view.php?id=']", _ASSIGN_JS)
    except Exception:
        return []
    return [a for a in items if a.get("href")]


def _collect_section_pages(page, course_url: str) -> list[str]:
    """Enlaces a páginas de sección (formato 'una sección por página')."""
    try:
        hrefs = page.eval_on_selector_all(
            "a[href*='course/section.php'], a[href*='course/view.php']",
            "els => els.map(e => e.href.split('#')[0])",
        )
    except Exception:
        return []
    out, seen = [], set()
    for h in hrefs or []:
        if ("section.php?id=" in h
                or re.search(r"course/view\.php\?id=\d+.*[?&]section=\d+", h)):
            if h != course_url and h not in seen:
                seen.add(h)
                out.append(h)
    return out


def save_debug(html: str, debug_dir: str, name: str,
               log: logging.Logger | None = None) -> str:
    os.makedirs(debug_dir, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60] or "pagina"
    path = os.path.join(debug_dir, f"{safe}.html")
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)
    if log:
        log.warning(f"HTML de diagnóstico guardado en {path}")
    return path


def list_assigns_in_course(page, course_url: str,
                           log: logging.Logger | None = None,
                           debug_dir: str | None = None,
                           course_label: str = "") -> list[dict]:
    page.goto(course_url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector(
            "a[href*='mod/assign/view.php?id='], .course-content, #region-main",
            timeout=15000)
    except Exception:
        pass
    # Scroll completo: dispara la carga diferida de secciones/actividades.
    try:
        page.evaluate("""async () => {
          for (let y = 0; y < document.body.scrollHeight; y += 1200) {
            window.scrollTo(0, y);
            await new Promise(r => setTimeout(r, 120));
          }
          window.scrollTo(0, 0);
        }""")
    except Exception:
        pass
    page.wait_for_timeout(1000)

    found = _collect_assigns(page)
    seen = {a["href"] for a in found}

    # Fallback: formato 'una sección por página' -> visitar cada sección.
    if not found:
        for sec_url in _collect_section_pages(page, course_url):
            if log:
                log.info(f"   … revisando página de sección: {sec_url}")
            try:
                page.goto(sec_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
                for a in _collect_assigns(page):
                    if a["href"] not in seen:
                        seen.add(a["href"])
                        found.append(a)
            except Exception as e:
                if log:
                    log.warning(f"   … no pude abrir {sec_url}: {type(e).__name__}")

    if not found and log:
        try:
            title = page.title() or ""
        except Exception:
            title = ""
        try:
            n_links = page.eval_on_selector_all(
                "a[href]", "els => els.length")
        except Exception:
            n_links = "?"
        log.warning(
            f"   !! 0 tareas en {course_label or course_url} (página: {title!r}, "
            f"enlaces totales: {n_links}). Puede que el curso no tenga actividades "
            f"de tipo Tarea o aún esté vacío. Sigo con el siguiente curso.")
        if debug_dir:
            try:
                save_debug(page.content(), debug_dir,
                           f"curso_{course_label or 'sin_nombre'}", log)
            except Exception:
                pass
    return found
