"""Rutas de salida: ./salida/<Curso>/<tema>/<tarea>/ + aliases opcionales."""
from __future__ import annotations

import json
import os
import re

from .config import ALIASES_LOCAL_PATH, ALIASES_PATH, OUTPUT_DIR
from .naming import sanitize_component, snake_case


def load_aliases(path: str = ALIASES_PATH) -> dict[str, str]:
    """Junta aliases.json (genérico, se puede publicar) con aliases.local.json
    (tus nombres cortos, solo en tu máquina: está en .gitignore)."""
    merged: dict[str, str] = {}
    for p in (path, ALIASES_LOCAL_PATH):
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    merged.update(json.load(f))
            except (ValueError, OSError):
                pass
    return merged


def strip_teacher_prefix(name: str) -> str:
    """Quita prefijos tipo 'nombre.apellido_' que Moodle antepone al shortname.
    Solo si tiene forma usuario.usuario_ ; si no, devuelve el nombre intacto."""
    return re.sub(r"^[A-Za-zà-ÿ0-9-]+\.[A-Za-zà-ÿ0-9-]+_", "", name).strip("_ ")


def pretty_course(course_short: str, course_title: str, aliases: dict[str, str]) -> str:
    """1) aliases (local primero); 2) autodetección: title limpio o short sin
    prefijo de profesor; todo a snake_case válido."""
    for key in (course_short, course_title):
        if key and key in aliases:
            return sanitize_component(aliases[key])
    if course_title:
        cand = strip_teacher_prefix(course_title)
    elif course_short:
        cand = strip_teacher_prefix(course_short)
    else:
        cand = "curso"
    return sanitize_component(snake_case(cand) or "curso")


def task_dir(output: str, course: str, section: str, task: str) -> str:
    sec = sanitize_component(snake_case(section or "tema"))[:60] or "tema"
    # normaliza "UT02 INTRODUCCION..." -> "ut02_introduccion_al_lenguaje_java" -> acorta a tema? No:
    # el usuario pidió ./salida/Programacion/tema1/... ; mantenemos sección completa
    # pero si empieza por ut02 la dejamos (es su organización real).
    t = sanitize_component(snake_case(task or "tarea"))[:80] or "tarea"
    path = os.path.join(output, course, sec, t)
    os.makedirs(path, exist_ok=True)
    return path


def default_output() -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR
