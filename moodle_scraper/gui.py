"""Interfaz web local (solo librería estándar, mismo estilo que index.html).

Uso:
    .venv/bin/python -m moodle_scraper.gui [--port 8765] [-o salida]

Abre http://127.0.0.1:8765 con:
- Campo para la dirección del Aula Virtual (Moodle).
- Botón "Iniciar copia de seguridad" (equivale a --live, con registro en vivo).
- Botón "Regenerar página HTML" (equivale a --regen, sin descargar nada).
- Botón "Abrir informe" (sirve tu salida/index.html con sus archivos).
"""
from __future__ import annotations

import argparse
import collections
import functools
import html as _html
import http.server
import json
import logging
import os
import queue
import threading
import urllib.parse
import webbrowser

from . import config
from .gui_logic import validate_url  # noqa: F401  (reexportado para tests)
from .log import setup_log

OUTPUT = config.OUTPUT_DIR
PORT = 8765
EXAMPLE_URL = "https://moodle.com"

_log_lines: collections.deque[str] = collections.deque(maxlen=600)
_state = {"running": False, "task": "", "done_msg": ""}
_state_lock = threading.Lock()


class QueueHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        _log_lines.append(line)


def _set(running: bool, task: str = "", done_msg: str = "") -> None:
    with _state_lock:
        _state.update(running=running, task=task, done_msg=done_msg)


def _run_in_thread(target, *args) -> bool:
    with _state_lock:
        if _state["running"]:
            return False
    threading.Thread(target=_wrap, args=(target,) + args, daemon=True).start()
    return True


def _wrap(target, *args) -> None:
    try:
        target(*args)
        _set(False, done_msg="ok")
    except Exception as e:  # noqa: BLE001 - se muestra en la web
        _set(False, done_msg=f"error: {type(e).__name__}: {e}")


def _make_log(output: str) -> logging.Logger:
    os.makedirs(output, exist_ok=True)
    log = setup_log(output)
    h = QueueHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%H:%M:%S"))
    log.addHandler(h)
    return log


def start_backup(base_url: str, output: str) -> None:
    from .main import run_live
    log = _make_log(output)
    log.info(f"Copia de seguridad en {base_url} …")
    run_live(output, log=log, base_url=base_url)


def start_regen(output: str) -> None:
    from .report import regen_index
    log = _make_log(output)
    try:
        n_tareas, n_err = regen_index(output)
    except FileNotFoundError:
        raise FileNotFoundError(f"No existe {output}/resumen.json: nada que regenerar.")
    log.info(f"Página regenerada: {n_tareas} tareas, {n_err} errores.")


PAGE = """<!doctype html><html lang="es" data-theme="auto"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copia de seguridad · Aula Virtual</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2333;--muted:#667085;--line:#e2e6ee;--acc:#2456d6;--acc-ink:#fff;--ok:#137333;--err:#b42318;--field:#fff}
@media (prefers-color-scheme:dark){:root[data-theme="auto"]{--bg:#10141c;--card:#1a2130;--ink:#e8ecf4;--muted:#9aa4b8;--line:#2c3547;--acc:#7aa2ff;--acc-ink:#10141c;--ok:#7dd79a;--err:#ff9a92;--field:#10141c}}
:root[data-theme="dark"]{--bg:#10141c;--card:#1a2130;--ink:#e8ecf4;--muted:#9aa4b8;--line:#2c3547;--acc:#7aa2ff;--acc-ink:#10141c;--ok:#7dd79a;--err:#ff9a92;--field:#10141c}
*{box-sizing:border-box}body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);margin:0;padding:0 1rem 3rem}
.wrap{max-width:820px;margin:0 auto}
header{display:flex;align-items:center;gap:.75rem;padding:1.2rem 0 .4rem}
header h1{font-size:1.35rem;margin:0;flex:1}
#themeBtn{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:.35rem .8rem;cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:.7rem;padding:.9rem 1rem;margin:.8rem 0}
.card h2{font-size:.95rem;margin:0 0 .6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
input[type=url]{width:100%;padding:.55rem .7rem;border:1px solid var(--line);border-radius:.5rem;background:var(--field);color:var(--ink);font-size:.95rem}
.row{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.6rem}
button.act{background:var(--acc);color:var(--acc-ink);border:none;border-radius:.55rem;padding:.6rem 1.1rem;font-size:.95rem;cursor:pointer}
button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line);border-radius:.55rem;padding:.6rem 1.1rem;font-size:.95rem;cursor:pointer}
button:disabled{opacity:.45;cursor:default}
#status{font-size:.9rem;margin:.2rem 0}
.pill{display:inline-block;border-radius:999px;padding:.15rem .7rem;font-size:.8rem;font-weight:600}
.pill.idle{background:var(--line)}
.pill.run{background:var(--acc);color:var(--acc-ink)}
.pill.ok{background:var(--ok);color:#fff}
.pill.err{background:var(--err);color:#fff}
#log{background:#0b0e14;color:#d6deeb;border-radius:.55rem;padding:.7rem .8rem;height:300px;overflow-y:auto;font-family:ui-monospace,Consolas,monospace;font-size:.8rem;white-space:pre-wrap;margin:0}
small.hint{color:var(--muted)}
</style></head><body><div class="wrap">
<header><h1>📚 Copia de seguridad · Aula Virtual</h1><button id="themeBtn" class="ghost">🌓</button></header>
<div class="card"><h2>Sitio web</h2>
<input id="url" type="url" value="" placeholder="__BASE__">
<div class="row">
<button class="act" id="bBackup">⬇ Iniciar copia de seguridad</button>
<button class="ghost" id="bRegen">🔄 Regenerar página HTML</button>
<button class="ghost" id="bOpen">📄 Abrir informe</button>
</div>
<div class="row"><small class="hint">La copia abre Chromium para login manual y puede tardar minutos. Regenerar solo rehace el HTML, sin descargar.</small></div>
</div>
<div class="card"><h2>Progreso <span id="pill" class="pill idle">listo</span></h2>
<p id="status">Pulsa «Iniciar copia de seguridad».</p></div>
<div class="card"><h2>Registro en vivo</h2><p id="log"></p></div>
</div>
<script>
"use strict";
var seen = 0, timer = null;
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
async function poll(){
  try{
    var r = await fetch("/api/state?since=" + seen);
    var s = await r.json();
    seen = s.total;
    var box = document.getElementById("log");
    s.lines.forEach(function(l){box.textContent += l + "\\n";});
    box.scrollTop = box.scrollHeight;
    var pill = document.getElementById("pill"), st = document.getElementById("status");
    document.getElementById("bBackup").disabled = s.running;
    document.getElementById("bRegen").disabled = s.running;
    if(s.running){pill.className = "pill run"; pill.textContent = "en marcha";
      if(s.last) st.textContent = s.last;}
    else if(s.done_msg){
      if(s.done_msg === "ok"){pill.className = "pill ok"; pill.textContent = "terminado";
        st.textContent = "Hecho. Abre el informe con «📄 Abrir informe».";}
      else{pill.className = "pill err"; pill.textContent = "error"; st.textContent = s.done_msg;}
    }
  }catch(e){}
}
async function post(path, body){
  var r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})});
  var j = await r.json();
  if(!j.ok) alert(j.error || "No se pudo iniciar (¿ya hay una tarea en marcha?)");
  poll();
}
document.getElementById("bBackup").addEventListener("click", function(){
  var u = document.getElementById("url").value.trim();
  if(!/^https?:\\/\\//i.test(u)){alert("La dirección debe empezar por http:// o https://"); return;}
  if(!confirm("Se abrirá Chromium para login manual en\\n" + u + "\\n¿Continuar?")) return;
  post("/api/backup", {url: u});
});
document.getElementById("bRegen").addEventListener("click", function(){post("/api/regen", {});});
document.getElementById("bOpen").addEventListener("click", function(){window.open("/salida/index.html", "_blank");});
document.getElementById("themeBtn").addEventListener("click", function(){
  var h = document.documentElement, cur = h.getAttribute("data-theme") || "auto";
  h.setAttribute("data-theme", cur === "auto" ? "light" : cur === "light" ? "dark" : "auto");
});
timer = setInterval(poll, 600); poll();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    output = OUTPUT
    server_version = "AulaBackup/1.0"

    def log_message(self, *args):  # silencioso: el registro va en la web
        pass

    def _json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            body = PAGE.replace("__BASE__", _html.escape(EXAMPLE_URL)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/state":
            try:
                since = int(urllib.parse.parse_qs(parsed.query).get("since", ["0"])[0])
            except ValueError:
                since = 0
            lines = list(_log_lines)
            total = len(_log_lines)
            # deque con maxlen: 'since' puede referirse a líneas ya descartadas
            new = lines[max(0, since - (total - len(lines))):] if since <= total else lines
            with _state_lock:
                st = dict(_state)
            st.update(lines=new, total=total, last=lines[-1] if lines else "")
            self._json(st)
        elif parsed.path == "/salida/index.html" or parsed.path.startswith("/salida/"):
            self._serve_output(parsed.path[len("/salida/"):])
        else:
            self.send_error(404)

    def _serve_output(self, rel: str) -> None:
        base = os.path.abspath(self.output)
        path = os.path.abspath(os.path.join(base, urllib.parse.unquote(rel)))
        if not path.startswith(base + os.sep) and path != base:
            self.send_error(404)
            return
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if not os.path.isfile(path):
            self.send_error(404, "Aún no hay informe: inicia una copia primero.")
            return
        ctype = "text/html; charset=utf-8" if path.endswith(".html") else "application/octet-stream"
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, OSError):
            data = {}
        if self.path == "/api/backup":
            from .gui_logic import validate_url
            try:
                base = validate_url(data.get("url", ""))
            except ValueError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            if not _run_in_thread(start_backup, base, self.output):
                return self._json({"ok": False, "error": "Ya hay una tarea en marcha."}, 409)
            _set(True, task="backup")
            return self._json({"ok": True})
        if self.path == "/api/regen":
            if not _run_in_thread(start_regen, self.output):
                return self._json({"ok": False, "error": "Ya hay una tarea en marcha."}, 409)
            _set(True, task="regen")
            return self._json({"ok": True})
        return self.send_error(404)


def serve(port: int = PORT, output: str = OUTPUT, open_browser: bool = True) -> None:
    Handler.output = os.path.abspath(output)
    os.makedirs(Handler.output, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Interfaz en {url}  (Ctrl+C para salir)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Interfaz web local de la copia de seguridad")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("-o", "--output", default=OUTPUT)
    args = ap.parse_args()
    serve(args.port, args.output)


if __name__ == "__main__":
    main()
