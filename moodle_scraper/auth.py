"""Auth 100% manual: abre Chromium, el usuario loguea, reutilizamos la sesión solo en memoria."""
from __future__ import annotations

import logging
import threading
import time


def _login_detected(page) -> bool:
    """Heurística tolerante: ¿se ve ya la sesión iniciada? Nunca lanza excepción."""
    try:
        if page.locator("a[href*='login/logout']").count() > 0:
            return True
    except Exception:
        pass
    try:
        if page.get_by_text("Cerrar sesión", exact=False).count() > 0:
            return True
    except Exception:
        pass
    try:
        url = page.url or ""
        title = page.title() or ""
        if "login/index.php" not in url and ("/my/" in url or "Mis cursos" in title):
            return True
    except Exception:
        pass
    return False


def login_manual(playwright, base_url: str, log: logging.Logger | None = None,
                 timeout_min: float = 15):
    """Devuelve (browser, context, page) ya logueado. Cierra con browser.close() el llamador.

    No bloquea nunca sin avisar: detecta el login solo y sigue automáticamente.
    ENTER sirve como respaldo (2 veces fuerza continuar aunque no detecte sesión).
    Todo se registra en el log, no solo en consola.
    """
    log = log or logging.getLogger("moodle_scraper")
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log.error(f"No pude abrir {base_url}: {type(e).__name__}: {e}. "
                  f"Revisa tu conexión y vuelve a intentarlo.")
        browser.close()
        raise
    log.info("Ventana Chromium abierta: inicia sesión MANUALMENTE en ella.")
    log.info("Sigo solo cuando detecte tu sesión. Atajo: pulsa ENTER aquí "
             "(2 veces seguidas fuerza continuar).")

    entered = threading.Event()

    def _wait_enter() -> None:
        try:
            input(">> ENTER cuando hayas iniciado sesión (normalmente no hace falta: lo detecto solo)... ")
        except EOFError:
            pass
        except Exception:
            pass
        entered.set()

    def _arm() -> None:
        entered.clear()
        threading.Thread(target=_wait_enter, daemon=True).start()

    _arm()
    forces = 0
    deadline = time.time() + timeout_min * 60
    # chequeo inmediato por si la sesión ya estaba abierta
    while True:
        if _login_detected(page):
            try:
                who = page.title() or ""
                log.info(f"Sesión detectada ({who[:60]}). Sigo con la descarga...")
            except Exception:
                log.info("Sesión detectada. Sigo con la descarga...")
            return browser, context, page
        if entered.is_set():
            forces += 1
            if _login_detected(page):
                log.info("Sesión confirmada con ENTER. Sigo...")
                return browser, context, page
            if forces >= 2:
                log.warning("Forzando continuar sin sesión detectada (pedido con doble ENTER). "
                            "Si ves errores de login, reinicia el programa.")
                return browser, context, page
            log.warning("ENTER recibido pero aún no detecto tu sesión "
                        "(¿ves tu nombre / 'Mis cursos' en la ventana?). "
                        "Espero al login... pulsa ENTER otra vez para forzar.")
            _arm()
        if time.time() > deadline:
            browser.close()
            raise TimeoutError(
                f"Sin login tras {timeout_min:g} min. Cierro el navegador; "
                f"vuelve a ejecutar el programa e inicia sesión en la ventana.")
        time.sleep(1)


def cookies_header(context) -> str:
    cookies = context.cookies()
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
