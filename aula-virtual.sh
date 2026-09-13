#!/usr/bin/env bash
# Lanzador auto-instalable (Linux) — doble clic o ./aula-virtual.sh
# Crea .venv e instala deps solo la primera vez, luego abre la interfaz web.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  echo "Uso: $0 [puerto] [carpeta_salida]"
  echo "  Ej: $0 8765 salida"
  exit 0
fi
PORT="${1:-8765}"
OUT="${2:-salida}"

find_python() {
  for c in "python3" "python" "py"; do
    if command -v "$c" >/dev/null 2>&1 && "$c" --version >/dev/null 2>&1; then echo "$c"; return 0; fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "$PY" ]; then
  echo "No encontré Python. Instálalo (sudo pacman -S python / sudo apt install python3) y vuelve a ejecutar."
  read -p "Pulsa Enter para salir..." _; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creando entorno .venv..."
  "$PY" -m venv .venv
fi
VPY=".venv/bin/python"

need=1
if [ -f ".venv/installed.txt" ] && command -v sha256sum >/dev/null 2>&1; then
  a="$(sha256sum requirements.txt | cut -d' ' -f1)"
  b="$(head -n1 .venv/installed.txt 2>/dev/null || true)"
  if [ "$a" = "$b" ] && "$VPY" -c "import playwright" 2>/dev/null; then need=0; fi
fi
if [ "$need" -eq 1 ]; then
  echo "Instalando dependencias (solo la primera vez)..."
  "$VPY" -m pip install --upgrade pip
  "$VPY" -m pip install -r requirements.txt
  sha256sum requirements.txt | cut -d' ' -f1 > .venv/installed.txt || cp requirements.txt .venv/installed.txt
fi

# Si tienes Brave/Chrome, no descargo Chromium (ahorra ~650 MB)
has_brave=0
for p in /usr/bin/brave-browser /usr/bin/brave /snap/bin/brave /var/lib/flatpak/exports/bin/com.brave.Browser; do
  [ -x "$p" ] && has_brave=1
done
command -v brave-browser >/dev/null 2>&1 && has_brave=1
command -v brave >/dev/null 2>&1 && has_brave=1
if [ "$has_brave" -eq 0 ]; then
  echo "Descargando Chromium (solo primera vez)..."
  "$VPY" -m playwright install chromium || echo "Aviso: playwright install falló, intentaré usar tu navegador igual."
else
  echo "Brave/Chrome detectado: no descargo Chromium."
fi

echo "Abriendo interfaz en http://127.0.0.1:$PORT ..."
nohup "$VPY" -m moodle_scraper.gui --port "$PORT" -o "$OUT" >/tmp/aulavirtual.log 2>&1 &
sleep 1
if command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:$PORT/" >/dev/null 2>&1 || true
elif command -v gio >/dev/null 2>&1; then gio open "http://127.0.0.1:$PORT/" 2>/dev/null || true
else echo "Entra manualmente a http://127.0.0.1:$PORT/"; fi
