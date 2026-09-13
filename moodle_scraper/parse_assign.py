"""Parsea el HTML de una tarea Moodle (assign) tanto en vivo como desde fixture local.

No asume Moodle estándar: busca por textos en español y por patrones de URL,
con múltiples fallbacks.
"""
from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse


def _clean(text: str) -> str:
    text = _html.unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self) -> str:
        return _clean(" ".join(self.parts))


def html_to_text(fragment: str) -> str:
    p = _TextExtractor()
    p.feed(fragment or "")
    return p.text()


def _find_grade(raw: str) -> str | None:
    # 1) Preferir tabla de feedback (.feedbacktable) para no coger otras menciones
    m = re.search(
        r'class="[^"]*feedbacktable[^"]*"[^>]*>.*?<th[^>]*>\s*Calificaci.n\s*</th>\s*<td[^>]*>(.*?)</td>',
        raw, re.S | re.I)
    if m:
        t = html_to_text(m.group(1))
        if t and t.lower() not in ("calificado", "sin calificar", "-"):
            return t
    # 2) Fallback: cualquier th Calificación + td
    for m in re.finditer(
        r'<th[^>]*>\s*Calificaci.n\s*</th>\s*<td[^>]*>(.*?)</td>', raw, re.S | re.I):
        t = html_to_text(m.group(1))
        # descartar estados, quedarse con algo que parezca nota (digito o letra)
        if t and re.search(r"\d|[a-zA-Z]", t):
            # evitar "Calificado sobre..." que no es nota: debe contener / o numero o Sin
            if re.search(r"\d|/|apto|bien|notable|sobresaliente|sin", t, re.I):
                # la primera coincidencia válida dentro de feedback suele ser la buena;
                # si hay varias, la que tiene '/' es la nota
                if "/" in t or re.match(r"^\d", t):
                    return t
    return None


def _find_feedback(raw: str) -> str:
    # Preferir versión completa oculta, si no resumen
    m = re.search(
        r'class="[^"]*full_assignfeedback_comments_[^"]*"[^>]*>(.*?)</div>\s*<div[^>]*>\s*</div>\s*</td>',
        raw, re.S | re.I)
    if not m:
        m = re.search(
            r'<div[^>]*class="[^"]*full_assignfeedback_comments_[^"]*"[^>]*>(.*?)</div>\s*(?:<a|</td)',
            raw, re.S | re.I)
    # fallback más simple: coger el div full entero
    if not m:
        m = re.search(
            r'class="[^"]*full_assignfeedback_comments_\d+[^"]*"[^>]*>(.*)',
            raw, re.S | re.I)
        if m:
            frag = m.group(1)[:20000]
            # cortar en el cierre de la tabla de feedback
            cut = re.search(r"</table>", frag, re.I)
            frag = frag[: cut.start()] if cut else frag
            t = html_to_text(frag)
            if len(t) > 20:
                return t
    if m:
        t = html_to_text(m.group(1))
        if len(t) > 10:
            return t
    m = re.search(
        r'class="[^"]*summary_assignfeedback_comments_\d+[^"]*"[^>]*>(.*?)</div>',
        raw, re.S | re.I)
    if m:
        return html_to_text(m.group(1))
    return ""


def _find_files(raw: str) -> list[dict]:
    """Todos los pluginfile.php con su nombre visible. Clasifica por URL."""
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<a[^>]*href="([^"]*pluginfile\.php[^"]*)"[^>]*>(.*?)</a>', raw, re.S | re.I):
        url = _html.unescape(m.group(1)).replace("&amp;", "&")
        name = _clean(re.sub(r"<[^>]+>", " ", m.group(2)))
        if not name or name.lower() in ("ver completo", "vea el resumen"):
            continue
        if url in seen:
            continue
        seen.add(url)
        if "introattachment" in url:
            kind = "enunciado"
        elif "assignsubmission_file" in url:
            kind = "entrega"
        elif "assignfeedback" in url:
            kind = "retroalimentacion_adjunto"
        else:
            kind = "otro"
        # nombre real suele ir al final de la URL
        try:
            tail = unquote(urlparse(url).path.rsplit("/", 1)[-1])
            if tail and "." in tail and not name.strip():
                name = tail
        except Exception:
            pass
        out.append({"filename": name, "url": url, "kind": kind})
    return out


def _find_online_text(raw: str) -> tuple[str, list[str]]:
    m = re.search(
        r'assignsubmission_onlinetext[^>]*>(.*?)</div>\s*</div>\s*</td>',
        raw, re.S | re.I | re.DOTALL)
    if not m:
        # fallback: div onlinetext generico
        m = re.search(r'onlinetext[^>]*>(.{20,8000}?)</div>', raw, re.S | re.I)
    if not m:
        return "", []
    frag = m.group(1)
    links = [_html.unescape(u).replace("&amp;", "&")
             for u in re.findall(r'href="([^"]+)"', frag)]
    links = [u for u in links if u.startswith("http")]
    return html_to_text(frag), links


def _breadcrumb(raw: str) -> tuple[str, str, str]:
    """Devuelve (course_short, course_title_attr, section_name)."""
    # Ámbito breadcrumb primero (evita coger secciones del índice lateral)
    crumb = ""
    m_nav = re.search(
        r'<nav[^>]*aria-label="Camino de migas"[^>]*>(.*?)</nav>', raw, re.S | re.I)
    if m_nav:
        crumb = m_nav.group(1)
    if not crumb:
        m_ol = re.search(
            r'<ol[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>(.*?)</ol>', raw, re.S | re.I)
        if m_ol:
            crumb = m_ol.group(1)
    scope = crumb or raw
    course_short, course_title = "", ""
    m = re.search(
        r'<a[^>]*href="[^"]*course/view\.php\?id=\d+"[^>]*title="([^"]*)"[^>]*>(.*?)</a>',
        scope, re.S | re.I)
    if m:
        course_title = _clean(m.group(1))
        course_short = _clean(re.sub(r"<[^>]+>", " ", m.group(2)))
    else:
        # title antes que href, o enlace sin title
        m = re.search(
            r'<a[^>]*title="([^"]*)"[^>]*href="[^"]*course/view\.php\?id=\d+"[^>]*>(.*?)</a>',
            scope, re.S | re.I)
        if m:
            course_title = _clean(m.group(1))
            course_short = _clean(re.sub(r"<[^>]+>", " ", m.group(2)))
        else:
            m3 = re.search(
                r'<a[^>]*href="[^"]*course/view\.php\?id=\d+"[^>]*>(.*?)</a>',
                scope, re.S | re.I)
            if m3:
                course_short = _clean(re.sub(r"<[^>]+>", " ", m3.group(1)))
    secs = re.findall(
        r'course/section\.php\?id=\d+"[^>]*>(.*?)</a>', scope, re.S | re.I)
    section = _clean(re.sub(r"<[^>]+>", " ", secs[-1])) if secs else ""
    if not section:
        # fallback global: última sección UTxx (no General del índice)
        all_secs = re.findall(
            r'course/section\.php\?id=\d+"[^>]*>(.*?)</a>', raw, re.S | re.I)
        cands = [_clean(re.sub(r"<[^>]+>", " ", s)) for s in all_secs]
        uts = [c for c in cands if re.match(r"(?i)ut\d+|tema\s*\d+", c)]
        section = uts[-1] if uts else (cands[-1] if cands else "")
    return course_short, course_title, section


def parse_assignment_html(html: str, url: str = "") -> dict:
    task = ""
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
    if m:
        task = _clean(re.sub(r"<[^>]+>", " ", m.group(1)))
    course_short, course_title, section = _breadcrumb(html)
    grade_raw = _find_grade(html)
    feedback = _find_feedback(html)
    files = _find_files(html)
    online_text, online_links = _find_online_text(html)
    # descripción: activity-description sin los links de ficheros
    desc = ""
    m = re.search(
        r'<div[^>]*class="[^"]*activity-description[^"]*"[^>]*id="intro"[^>]*>(.*?)</div>\s*</div>',
        html, re.S | re.I)
    if m:
        desc = html_to_text(m.group(1))
    task_id = ""
    mm = re.search(r"[?&]id=(\d+)", url)
    if mm:
        task_id = mm.group(1)
    return {
        "task_name": task,
        "task_id": task_id,
        "task_url": url,
        "course_short": course_short,
        "course_title": course_title,
        "section": section,
        "grade_raw": grade_raw,
        "feedback": feedback,
        "files": files,
        "online_text": online_text,
        "online_links": online_links,
        "description": desc,
    }
