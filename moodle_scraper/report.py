"""resumen.json + index.html (autocontenido, sin internet) + errores_para_manual.txt"""
from __future__ import annotations

import datetime
import html as _html
import json
import os
import re
from urllib.parse import quote

from .naming import grade_percent

_KIND_ICON = {
    "entrega": "\U0001F4C4",
    "enunciado": "\U0001F4DD",
    "retroalimentacion_adjunto": "\U0001F4CE",
    "feedback": "\U0001F4AC",
    "online": "\U0001F517",
    "otro": "\U0001F4E6",
}


def save_report(entries: list[dict], errors: list[dict], output: str) -> None:
    os.makedirs(output, exist_ok=True)
    with open(os.path.join(output, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    with open(os.path.join(output, "errores_para_manual.txt"), "w", encoding="utf-8") as f:
        if not errors:
            f.write("Sin errores. Todo descargado.\n")
        for e in errors:
            f.write(f"- [{e.get('curso')}/{e.get('tarea')}] {e.get('archivo')} :: {e.get('motivo')} :: {e.get('url','')}\n")
    _write_html(entries, errors, output)


def regen_index(output: str) -> tuple[int, int]:
    """Regenera SOLO index.html a partir de resumen.json (+ errores_para_manual.txt).

    No toca ningún archivo descargado. Rellena 'nota_pct' si falta (informes
    generados con versiones anteriores) y lo persiste en resumen.json.
    Devuelve (n_tareas, n_errores).
    """
    with open(os.path.join(output, "resumen.json"), encoding="utf-8") as f:
        entries = json.load(f)
    touched = False
    for e in entries:
        if "nota_pct" not in e:
            e["nota_pct"] = grade_percent(e.get("nota"))
            touched = True
    if touched:
        with open(os.path.join(output, "resumen.json"), "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    errors = _read_errors_txt(os.path.join(output, "errores_para_manual.txt"))
    _write_html(entries, errors, output)
    return len(entries), len(errors)


def _read_errors_txt(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    errors: list[dict] = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"^-\s*\[(.*?)/(.*?)\]\s*(.*?)\s*::\s*(.*?)\s*::\s*(.*)$", line)
            if m:
                errors.append({"curso": m.group(1), "tarea": m.group(2),
                               "archivo": m.group(3), "motivo": m.group(4),
                               "url": m.group(5)})
    return errors


def _write_html(entries: list[dict], errors: list[dict], output: str) -> None:
    for e in entries:
        for a in e.get("archivos", []):
            a["href"] = quote(f"{e.get('carpeta', '')}/{a.get('final', '')}", safe="/")
            a["icono"] = _KIND_ICON.get(a.get("tipo"), "\U0001F4E6")
    payload = json.dumps({"entries": entries, "errors": errors}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    page = _SHELL.replace("__PAYLOAD__", payload).replace("__GENERATED__", _html.escape(generated))
    with open(os.path.join(output, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


_SHELL = """<!doctype html>
<html lang="es" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mis entregas · Aula Virtual</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2333;--muted:#667085;--line:#e2e6ee;--acc:#2456d6;--acc-ink:#fff;--ok:#137333;--warn:#b54708;--chip:#eef2ff}
@media (prefers-color-scheme:dark){:root[data-theme="auto"]{--bg:#10141c;--card:#1a2130;--ink:#e8ecf4;--muted:#9aa4b8;--line:#2c3547;--acc:#7aa2ff;--acc-ink:#10141c;--ok:#7dd79a;--warn:#f5b04c;--chip:#232f4a}}
:root[data-theme="dark"]{--bg:#10141c;--card:#1a2130;--ink:#e8ecf4;--muted:#9aa4b8;--line:#2c3547;--acc:#7aa2ff;--acc-ink:#10141c;--ok:#7dd79a;--warn:#f5b04c;--chip:#232f4a}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);margin:0;padding:0 1rem 3rem}
.wrap{max-width:1100px;margin:0 auto}
header.top{display:flex;align-items:center;gap:.75rem;padding:1.2rem 0 .4rem;flex-wrap:wrap}
header.top h1{font-size:1.35rem;margin:0;flex:1;min-width:200px}
header.top small{color:var(--muted)}
#themeBtn{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:.35rem .8rem;cursor:pointer;font-size:.85rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin:.8rem 0 1rem}
.stat{background:var(--card);border:1px solid var(--line);border-radius:.7rem;padding:.6rem .8rem}
.stat b{font-size:1.25rem;display:block}
.stat span{font-size:.78rem;color:var(--muted)}
.controls{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;margin:.4rem 0 .8rem}
#q{flex:1;min-width:180px;padding:.5rem .7rem;border:1px solid var(--line);border-radius:.5rem;background:var(--card);color:var(--ink)}
.chips{display:flex;gap:.4rem;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:.3rem .75rem;cursor:pointer;font-size:.82rem}
.chip[aria-pressed="true"]{background:var(--acc);border-color:var(--acc);color:var(--acc-ink);font-weight:600}
.chip small{opacity:.75}
h2{font-size:1.05rem;margin:1.4rem 0 .5rem}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:.7rem;overflow:hidden;font-size:.88rem}
th,td{border-bottom:1px solid var(--line);padding:.45rem .6rem;text-align:left;vertical-align:top}
th{background:var(--chip);user-select:none;white-space:nowrap}
#tbl th[data-k]{cursor:pointer}
#tbl th[data-k]:hover{color:var(--acc)}
tbody tr:hover{background:rgba(127,150,200,.12)}
td.nota{white-space:nowrap}
.bar{height:5px;border-radius:3px;background:var(--line);margin-top:3px;min-width:70px}
.bar i{display:block;height:100%;border-radius:3px;background:var(--ok)}
.sin{color:var(--warn)}
.files a{color:var(--acc);text-decoration:none;display:inline-block;margin:.1rem .5rem .1rem 0;font-size:.84rem;word-break:break-all}
.files a:hover{text-decoration:underline}
.count{color:var(--muted);font-size:.75rem}
#emptyRow td{text-align:center;color:var(--muted);padding:1.2rem}
.errs{background:var(--card);border:1px solid var(--line);border-radius:.7rem;padding:.7rem 1rem;font-size:.86rem}
.errs li{margin:.25rem 0}
.ok{color:var(--ok)}
footer{color:var(--muted);font-size:.78rem;margin-top:1.5rem}
@media (max-width:640px){td:nth-child(2),th:nth-child(2){display:none}}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
<h1>📚 Mis entregas · Aula Virtual</h1>
<button id="themeBtn" title="Cambiar tema">🌓 tema: auto</button>
</header>
<small>Generado el __GENERATED__ · archivo local, funciona sin internet · los enlaces abren tus archivos descargados</small>
<section class="stats" id="stats"></section>
<h2>Por curso</h2>
<table id="byCourse"><thead><tr><th>Curso</th><th>Tareas</th><th>Archivos</th><th>Con nota</th><th>Media</th></tr></thead><tbody></tbody></table>
<h2>Tareas <span class="count" id="shown"></span></h2>
<div class="controls">
<input id="q" type="search" placeholder="🔍 Buscar por tarea, tema, curso o archivo…" autocomplete="off">
<div class="chips" id="chips"></div>
</div>
<table id="tbl"><thead><tr>
<th data-k="curso">Curso</th><th data-k="tema">Tema</th><th data-k="tarea">Tarea</th><th data-k="nota">Nota</th><th>Archivos</th>
</tr></thead><tbody id="rows"></tbody></table>
<h2>⚠️ Errores para descarga manual <span class="count" id="errCount"></span></h2>
<div class="errs"><ul id="errList"></ul></div>
<footer>Backup personal · medias calculadas en % para comparar escalas 0–10 y 0–100 · las tareas “Sin nota” no entran en las medias.</footer>
</div>
<script type="application/json" id="data">__PAYLOAD__</script>
<script>
"use strict";
var DB = JSON.parse(document.getElementById("data").textContent);
var state = {q: "", curso: "__all__", sortK: "curso", sortD: 1};
function esc(s){return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function pctFmt(p){return p == null ? "—" : String(p).replace(".", ",") + " %";}
function pctOf(e){return (typeof e.nota_pct === "number") ? e.nota_pct : null;}
function filtered(){
  var q = state.q.trim().toLowerCase();
  return DB.entries.filter(function(e){
    if(state.curso !== "__all__" && e.curso !== state.curso) return false;
    if(!q) return true;
    var hay = [e.curso, e.tema, e.tarea].concat((e.archivos || []).map(function(a){return a.final + " " + a.original;})).join(" ").toLowerCase();
    return hay.indexOf(q) >= 0;
  });
}
function sortedRows(rows){
  var k = state.sortK, d = state.sortD;
  return rows.slice().sort(function(a, b){
    var va, vb;
    if(k === "nota"){va = pctOf(a); vb = pctOf(b);
      if(va == null && vb == null) return 0; if(va == null) return 1; if(vb == null) return -1;
      return (va - vb) * d;}
    if(k === "archivos"){return ((a.archivos || []).length - (b.archivos || []).length) * d;}
    va = (a[k] || "").toLowerCase(); vb = (b[k] || "").toLowerCase();
    return (va < vb ? -1 : va > vb ? 1 : 0) * d;
  });
}
function notaCell(e){
  var p = pctOf(e);
  if(p == null) return '<span class="sin">Sin nota</span>';
  return esc(e.nota) + '<div class="bar" title="' + esc(pctFmt(p)) + '"><i style="width:' + Math.max(0, Math.min(100, p)) + '%"></i></div>';
}
function filesCell(e){
  if(!e.archivos || !e.archivos.length) return '<span class="count">—</span>';
  return '<span class="files">' + e.archivos.map(function(a){
    return '<a href="' + esc(a.href) + '" title="original: ' + esc(a.original) + '">' + esc(a.icono || "") + " " + esc(a.final) + "</a>";
  }).join("") + "</span>";
}
function render(){
  var rows = sortedRows(filtered());
  var tb = document.getElementById("rows");
  if(!rows.length){tb.innerHTML = '<tr id="emptyRow"><td colspan="5">Sin resultados con ese filtro.</td></tr>';}
  else{tb.innerHTML = rows.map(function(e){
    return "<tr><td>" + esc(e.curso) + "</td><td>" + esc(e.tema) + "</td><td>" + esc(e.tarea) + "</td>" +
      '<td class="nota">' + notaCell(e) + "</td><td>" + filesCell(e) + "</td></tr>";
  }).join("");}
  document.getElementById("shown").textContent = "(" + rows.length + " de " + DB.entries.length + ")";
  document.querySelectorAll("#tbl th[data-k]").forEach(function(th){
    var k = th.getAttribute("data-k");
    th.textContent = th.textContent.replace(/ [▲▼]$/, "");
    if(k === state.sortK) th.textContent += state.sortD === 1 ? " ▲" : " ▼";
  });
}
function renderStats(){
  var n = DB.entries.length, graded = 0, sum = 0, files = 0, cursos = {};
  DB.entries.forEach(function(e){
    files += (e.archivos || []).length;
    var p = pctOf(e);
    if(p != null){graded++; sum += p;}
    var c = cursos[e.curso] || (cursos[e.curso] = {t: 0, f: 0, g: 0, s: 0});
    c.t++; c.f += (e.archivos || []).length;
    if(p != null){c.g++; c.s += p;}
  });
  var media = graded ? (sum / graded) : null;
  var cn = Object.keys(cursos).length;
  document.getElementById("stats").innerHTML =
    stat(n, "tareas") + stat(files, "archivos") + stat(cn, "cursos") +
    stat(graded + "/" + n, "con nota") +
    stat(media == null ? "—" : pctFmt(Math.round(media * 10) / 10), "media global") +
    stat(String(DB.errors.length), "errores");
  function stat(v, l){return '<div class="stat"><b>' + esc(v) + "</b><span>" + esc(l) + "</span></div>";}
  var tb = document.querySelector("#byCourse tbody");
  tb.innerHTML = Object.keys(cursos).sort().map(function(c){
    var x = cursos[c];
    return "<tr><td>" + esc(c) + "</td><td>" + x.t + "</td><td>" + x.f + "</td><td>" + x.g + "/" + x.t + "</td><td>" +
      (x.g ? esc(pctFmt(Math.round(x.s / x.g * 10) / 10)) : "—") + "</td></tr>";
  }).join("") || '<tr><td colspan="5">Sin datos.</td></tr>';
  var chips = document.getElementById("chips");
  var html = '<button class="chip" data-c="__all__" aria-pressed="' + (state.curso === "__all__") + '">Todos <small>' + n + "</small></button>";
  Object.keys(cursos).sort().forEach(function(c){
    html += '<button class="chip" data-c="' + esc(c) + '" aria-pressed="' + (state.curso === c) + '">' + esc(c) + " <small>" + cursos[c].t + "</small></button>";
  });
  chips.innerHTML = html;
  chips.querySelectorAll(".chip").forEach(function(ch){
    ch.addEventListener("click", function(){state.curso = ch.getAttribute("data-c"); renderStats(); render();});
  });
  var ne = DB.errors.length;
  document.getElementById("errCount").textContent = "(" + ne + ")";
  document.getElementById("errList").innerHTML = ne ? DB.errors.map(function(x){
    return "<li>[" + esc(x.curso) + " / " + esc(x.tarea) + "] " + esc(x.archivo) + " — " + esc(x.motivo) + "</li>";
  }).join("") : '<li class="ok">Ninguno 🎉</li>';
}
document.getElementById("q").addEventListener("input", function(ev){state.q = ev.target.value; render();});
document.querySelectorAll("#tbl th[data-k]").forEach(function(th){
  th.addEventListener("click", function(){
    var k = th.getAttribute("data-k");
    if(state.sortK === k){state.sortD = -state.sortD;} else {state.sortK = k; state.sortD = 1;}
    render();
  });
});
(function theme(){
  var btn = document.getElementById("themeBtn"), root = document.documentElement;
  var names = {auto: "auto", light: "claro", dark: "oscuro"};
  var cur = "auto";
  try{cur = localStorage.getItem("moodle-theme") || "auto";}catch(e){cur = "auto";}
  if(names[cur] == null) cur = "auto";
  function apply(){
    root.setAttribute("data-theme", cur);
    btn.textContent = "🌓 tema: " + names[cur];
  }
  btn.addEventListener("click", function(){
    cur = cur === "auto" ? "light" : cur === "light" ? "dark" : "auto";
    try{localStorage.setItem("moodle-theme", cur);}catch(e){}
    apply();
  });
  apply();
})();
renderStats();
render();
</script>
</body>
</html>"""
