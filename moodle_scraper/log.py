"""Feedback de progreso: consola legible + fichero de log.

Niveles:
  - normal: qué curso/tarea/archivo se está procesando, con contadores [i/n].
  - verbose (--verbose): además pausas, reintentos, URLs y tiempos.
Todo queda también en <output>/backup.log
"""
from __future__ import annotations

import datetime
import logging
import os
import sys


def setup_log(output: str, verbose: bool = False) -> logging.Logger:
    os.makedirs(output, exist_ok=True)
    logger = logging.getLogger("moodle_scraper")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(os.path.join(output, "backup.log"), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    logger.info(f"Log guardado en {os.path.join(output, 'backup.log')} "
                f"({datetime.datetime.now():%Y-%m-%d %H:%M})")
    return logger


def fmt_size(n: int | None) -> str:
    if n is None or n < 0:
        return "?"
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"
