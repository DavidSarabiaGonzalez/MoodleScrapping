"""Descarga con reintentos, pausas anti-baneo y deduplicación por tamaño."""
from __future__ import annotations

import logging
import os
import random
import time
import urllib.request

from .config import MAX_RETRIES, REQUEST_DELAY_MAX, REQUEST_DELAY_MIN, RETRY_BACKOFF
from .log import fmt_size


def polite_pause(log: logging.Logger | None = None, verbose: bool = False) -> None:
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    if verbose and log:
        log.debug(f"pausa anti-baneo {delay:.1f}s...")
    time.sleep(delay)


def download_url(url: str, dest: str, cookies: str = "", timeout: int = 60,
                 log: logging.Logger | None = None,
                 label: str = "") -> tuple[bool, str]:
    """Descarga url -> dest mostrando progreso. Si existe con mismo tamaño, skip."""
    name = label or os.path.basename(dest)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if log and attempt > 1:
                log.warning(f"  ↻ reintento {attempt}/{MAX_RETRIES}: {name}")
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (MoodleScrapping personal backup)",
                "Cookie": cookies,
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                total = r.getheader("Content-Length")
                total = int(total) if total and total.isdigit() else None
                read = 0
                chunks: list[bytes] = []
                last_pct = -1
                while True:
                    buf = r.read(256 * 1024)
                    if not buf:
                        break
                    chunks.append(buf)
                    read += len(buf)
                    if log and total:
                        pct = int(read * 100 / total)
                        # avisa cada 25% para no spamear
                        if pct // 25 != last_pct // 25:
                            last_pct = pct
                            log.info(f"    ⬇ {name}: {pct}% ({fmt_size(read)}/{fmt_size(total)})")
                    elif log and read % (2 * 1024 * 1024) < 256 * 1024:
                        log.info(f"    ⬇ {name}: {fmt_size(read)} descargados...")
                data = b"".join(chunks)
            # dedup por tamaño
            if os.path.exists(dest) and os.path.getsize(dest) == len(data):
                if log:
                    log.info(f"    ＝ {name}: ya existe ({fmt_size(len(data))}), se salta")
                return True, "ya_existe_mismo_tamano"
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            if log:
                tag = "sobrescrito" if os.path.exists(dest) else "descargado"
                log.info(f"    ✓ {name}: {tag} ({fmt_size(len(data))})")
            return True, "descargado"
        except Exception as e:  # noqa: BLE001 - queremos seguir con el resto
            if log:
                log.warning(f"    ✗ {name} intento {attempt}/{MAX_RETRIES}: {type(e).__name__}: {e}")
            if attempt >= MAX_RETRIES:
                return False, f"{type(e).__name__}: {e}"
            time.sleep(RETRY_BACKOFF * attempt)
    return False, "reintentos_agotados"
