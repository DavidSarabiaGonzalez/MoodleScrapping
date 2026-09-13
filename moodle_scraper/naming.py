"""Normalizado de nombres: snake_case + [nota], válido Windows y Linux."""
from __future__ import annotations

import re
import unicodedata

from .config import LABEL_NO_GRADE, MAX_FILENAME_LEN

_RESERVED = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def snake_case(text: str) -> str:
    """Minusculas, sin acentos, no alfanumerico -> _. Colapsa y recorta."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "sin_nombre"


def sanitize_component(text: str, max_len: int = MAX_FILENAME_LEN) -> str:
    """Quita caracteres prohibidos en Windows/Linux y limita longitud."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = text.strip(" .")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .")
    if text.lower() in _RESERVED:
        text = f"_{text}"
    return text or "sin_nombre"


def normalize_grade(grade_raw: str | None) -> str:
    """'7,00 / 10,00' -> '7,00_10,00'. None/vacio -> 'Sin nota'."""
    if not grade_raw or not grade_raw.strip():
        return LABEL_NO_GRADE
    g = grade_raw.strip()
    g = re.sub(r"\s+", " ", g)
    g = g.replace("/", "_")
    g = g.replace(" ", "")
    g = re.sub(r"[<>:\"\\|?*\x00-\x1f]", "", g)
    g = re.sub(r"_+", "_", g).strip(" _.").strip()
    return g or LABEL_NO_GRADE


def grade_percent(grade_raw: str | None) -> float | None:
    """'7,00 / 10,00' -> 70.0 ; '82 / 100' -> 82.0 ; None/'Sin nota' -> None.

    Solo cuando hay escala explícita 'X / Y' (tus cursos mezclan 0-10 y 0-100).
    Sin escala no se inventa nada: devuelve None y no entra en las medias.
    """
    if not grade_raw:
        return None
    m = re.search(r"(-?[\d.,]+)\s*/\s*(-?[\d.,]+)", grade_raw)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
        scale = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if scale == 0:
        return None
    return round(val / scale * 100, 1)


def build_filename(original: str, grade_raw: str | None) -> str:
    """'Trabajo Programacion IDE.pdf' + '7,00 / 10,00' -> 'trabajo_programacion_ide [7,00_10,00].pdf'."""
    if "." in original and not original.startswith("."):
        stem, ext = original.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = original, ""
    stem_snake = sanitize_component(snake_case(stem))
    grade = sanitize_component(normalize_grade(grade_raw), max_len=60)
    return f"{stem_snake} [{grade}]{ext.lower()}"


def unique_path(base_dir: str, filename: str, extra: str = "") -> str:
    """Si filename existe, añade sufijo extra (curso__tema__nota) o contador."""
    import os

    candidate = os.path.join(base_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    if extra:
        stem, ext = (filename.rsplit(".", 1) + [""])[:2]
        ext = f".{ext}" if ext else ""
        stem_only = stem[: MAX_FILENAME_LEN - len(extra) - 10]
        candidate2 = os.path.join(base_dir, f"{stem_only}__{extra}{ext}")
        if not os.path.exists(candidate2):
            return candidate2
        filename = f"{stem_only}__{extra}{ext}"
    stem, ext = (filename.rsplit(".", 1) + [""])[:2]
    ext = f".{ext}" if ext else ""
    for i in range(2, 1000):
        c = os.path.join(base_dir, f"{stem}__{i}{ext}")
        if not os.path.exists(c):
            return c
    return candidate
