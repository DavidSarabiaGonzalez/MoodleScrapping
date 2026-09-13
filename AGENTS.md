# AGENTS.md — Context for AI agents continuing this project

> **Read this first.** It captures decisions, constraints and gotchas you need to extend the app without re-asking the user or breaking privacy/performance.

## 1. What this is

- **Goal:** personal backup of *Moodle* assignments (`mod/assign`) from **Aula Virtual de MurciaEduca** (`https://aulavirtual.murciaeduca.es`, Spanish, Moodle ~4.5) with history of submissions.
- **Outcomes per task:** downloaded files (submission + teacher material + rubric), grade baked into filename (`name [7,00_10,00].pdf`), feedback, `resumen.json`, self-contained `index.html` (offline), `errores_para_manual.txt`.
- **Not in scope:** Moodle Web Services are not assumed; browser automation is the reliable path (mobile app may/may not be enabled per centre).

## 2. Stack & versions

- **Python 3.14.7**, `.venv` + `pip`. `requirements.txt`: `playwright>=1.44`, `beautifulsoup4>=4.12`, `lxml>=5.0` (parsers currently use stdlib regex/`html.parser` so deps are light but keep them).
- **Playwright** with Chromium. **Brave-first**: `auth.py:_find_brave()` tries system Brave (`BRAVE_PATH` env, Windows `Program Files\BraveSoftware\...`, Linux `/usr/bin/brave-browser`/which), then `channel=chrome/msedge`, then Playwright Chromium.
- **OS:** CachyOS/Arch Linux dev host, targets **Windows + Linux** users via auto-installable launchers (no manual Python).
- **No embedded passwords.** Login is always **manual** in a Playwright window; session is reused in-memory via cookies only.

## 3. Repo layout (15 tracked files + generated)

```
moodle_scraper/
  config.py       # BASE_URL, OUTPUT_DIR, FIXTURES_DIR, ALIASES_PATH/_LOCAL, delays, filename limits, Spanish labels
  auth.py         # login_manual(), _find_brave(), _launch_browser(), cookies_header()
  courses.py      # list_courses(), list_assigns_in_course(), scroll/load, section-page fallback, save_debug()
  parse_assign.py # parse_assignment_html() — tolerant, Spanish labels, multiple fallbacks
  naming.py       # snake_case, sanitize_component, normalize_grade, build_filename, unique_path, grade_percent
  storage.py      # load_aliases() + merge, strip_teacher_prefix(), pretty_course(), task_dir()
  downloader.py   # polite_pause, download_url() with retry/backoff, size-based dedup, progress via logger
  log.py          # setup_log(), fmt_size()
  report.py       # save_report(), regen_index(), _write_html() (self-contained index.html)
  gui_logic.py    # validate_url() — pure, testable
  gui.py          # web UI (stdlib http.server) serving / , /api/* , /salida/*
  main.py         # CLI orchestrator: --live, --from-fixture, --all-fixtures, --regen, --url, -v
aliases.json        # public, MUST stay {} (empty). Never commit real names.
aliases.local.json  # private, .gitignored, user short names e.g. "Despliegue..." -> "despliegue"
AulaVirtual.ps1 / .bat / .vbs , aula-virtual.sh  # launchers (see §9)
fixtures_html/      # local HTML snapshots (Ctrl+S, only HTML) — .gitignored, used for offline parsing
salida/             # output — .gitignored (except private branch/completo)
requirements.txt / README.md / AGENTS.md
```

## 4. Configuration (`config.py:1`)

- `BASE_URL = "https://aulavirtual.murciaeduca.es"`, `OUTPUT_DIR = "./salida"`, `FIXTURES_DIR = "./fixtures_html"`, `ALIASES_PATH = "./aliases.json"`, `ALIASES_LOCAL_PATH = "./aliases.local.json"`.
- Network: `REQUEST_DELAY_MIN=1.0`, `MAX=2.5`, `MAX_RETRIES=3`, `RETRY_BACKOFF=2.0` (anti-ban), `MAX_FILENAME_LEN=150`.
- Labels: `Calificación`, `Archivos enviados`, `Comentarios de retroalimentación`, `Sin nota` — parse keys off these, not CSS.
- Theme colours / EXAMPLE_URL (`https://moodle.com`) live in `gui.py`.

## 5. CLI & web UI

- **CLI:** `python -m moodle_scraper.main [--live] [--url URL] [--regen] [--from-fixture PATH] [--all-fixtures] [-o salida] [-v]` — see `main.py:215`.
  - `--live` needs manual login; `--regen` only rebuilds `index.html` from existing `resumen.json`; fixtures are offline and never hit the server.
  - `--url` overrides `BASE_URL` for other Moodles.
- **Web UI:** `python -m moodle_scraper.gui [--port 8765] [-o salida]` — serves `/` (control page), `/api/backup`, `/api/regen`, `/api/state`, `/salida/*`. `EXAMPLE_URL` is placeholder only; input is validated by `gui_logic.validate_url()` (must start with `http(s)://`). Progress is streamed via `QueueHandler` + polling.

## 6. Browser automation & navigation

- **`auth.py:32`** `login_manual(playwright, base_url, log, timeout_min=15)` — launches via `_launch_browser`, auto-detects logged session (`a[href*=login/logout]`, `Cerrar sesión`, URL/title), ENTER as fallback (2× forces continue), 15-min timeout, all via `log`.
- **`courses.py:154`** `list_courses` / `list_assigns_in_course`:
  - Wait for `a[href*='course/view.php?id=']` with `timeout=15000/60000`, scroll to trigger lazy load, collect `mod/assign/view.php?id=` links plus section name via `_ASSIGN_JS`.
  - If 0 assigns, visit section pages (`course/section.php`, `view.php?section=`). On 0 still, write `_debug/curso_*.html` and log warning — do not fail the run.
  - `save_debug()` stores HTML for manual inspection.
- **Download:** `downloader.py:download_url(url, dest, cookies, log, label)` — chunked read with `Content-Length` progress, dedup by size (`ya_existe_mismo_tamano` skips write), `.part` then `os.replace`, 2–3 retries with backoff, small random `polite_pause()` between files (1.0–2.5 s).

## 7. Parsing (`parse_assign.py:240`)

- Never assume standard Moodle HTML. Match by Spanish text: `Calificación` (prefer `.feedbacktable`), `Archivos enviados`, `Comentarios de retroalimentación`, breadcrumb `Camino de migas` / `breadcrumb`. Strip accents, collapse whitespace, HTML-entity decode.
- Extract: `task_name` (`<h1>`), `task_id` (`?id=`), `course_short/title/section` (breadcrumb), `grade_raw` (`"7,00 / 10,00"`), `feedback` (full hidden `full_assignfeedback_comments_*` then summary), `files` (`pluginfile.php` with kinds `enunciado`/`entrega`/`retroalimentacion_adjunto`), `online_text/links`, `description`.
- `grade_percent`/`normalize_grade` in `naming.py` handle `7,00 / 10,00` → `7,00_10,00` in filename and `_` for slashes/spaces; commas kept.

## 8. Storage, naming, aliases

- **Layout:** `./salida/<curso>/<tema>/<tarea>/` — all components go through `snake_case` + `sanitize_component` (Windows `<>:"/\\|?*` + control chars, truncated, RESERVED like `CON` handled). `MAX_FILENAME_LEN` caps stem; extension lowercased.
- **Filename:** `build_filename(original, grade_raw)` → `trabajo_prog [7,00_10,00].pdf` or `[Sin nota]`; collisions → `unique_path(..., extra="curso_nota")` or counter.
- **Aliases:** `storage.py:load_aliases()` merges `aliases.json` (public empty) + `aliases.local.json` (private, 9 entries by default for this user). **Never commit real course/teacher names to `aliases.json`** — put them in `.local.json`. `pretty_course()` prefers alias, else `strip_teacher_prefix()` which removes `name.surname_` prefix via `^[A-Za-zà-ÿ0-9-]+\.[A-Za-zà-ÿ0-9-]+_` then snake_case. `task_dir()` caps section 60 / task 80.
- **Feedback:** saved as `<task>_feedback.txt` alongside files; `descripcion.txt` + `_online.txt` for text submissions.

## 9. Report & web index

- `report.py:279` `save_report(entries, errors, output)` writes `resumen.json` (entries with `nota_pct`), `errores_para_manual.txt`, and self-contained `index.html`.
- `regen_index(output)` re-adds `nota_pct` to old `resumen.json` and rebuilds only `index.html` (no downloads).
- `index.html` shell (`_SHELL`) is offline-cached: theme `auto/light/dark`, stats, per-course table, searchable/sortable/ filterable task table with file links (`href` = `quote(carpeta/final)`), `nota` % bar, error list. All interactive logic is inline — no CDN.

## 10. Launchers (cross-platform, no console)

- `AulaVirtual.ps1` (3.4 KB) — auto-creates `.venv`, pip install, Brave→Chrome detection to skip `playwright install chromium`, then `python -m moodle_scraper.gui --port …` hidden + open browser.
- `AulaVirtual.bat` (hidden `powershell -WindowStyle Hidden`), `AulaVirtual.vbs` (WScript.Shell), `aula-virtual.sh` (2.5 KB, `sha256sum` gate, `xdg-open`/`gio open`, `nohup`).
- `README.md:34` documents double-click usage; `.gitignore` keeps `salida/`, `fixtures_html/`, `aliases.local.json`, `*.log` private.

## 11. Git strategy & privacy

- **Two remotes:** `public` (`MoodleScrapping`, public, branch `main`, ~1 clean commit, 15 files) + `privado` (`MoodleScrapping-completo`, private, branch `completa` = `main` + `salida/` 590 files, ~262 MB, no file >100 MB).
- **Branch visibility is per-repo, not per-branch** — never push a branch with `salida/` to public. History was rewritten (`--orphan` + `--force`) to purge professor names; clones verify `SCAN_MAIN_DONE`.
- **Launchers are public-safe** (no personal data). Fixtures and `salida/_debug/*.html` contain `window.local_mail_navbar_data` with `userid`/`shortname` — keep them in private repo only.
- Scan before push: `git grep -niE "rosa|molinos|\.gil_|\.ortiz_|\.ferrer_|riquelme|sarabia|28219" main -- .` must be empty outside `salida`.

## 12. Development workflow

- Create venv: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt && .venv/bin/python -m playwright install chromium` (skip chromium if Brave present).
- Lint: `python -m py_compile moodle_scraper/*.py`, `bash -n aula-virtual.sh`.
- Offline check: `python -m moodle_scraper.main --from-fixture fixtures_html/tarea_ide_java.html -o /tmp/out_fx`.
- Regen check: `python -m moodle_scraper.main --regen -o salida`.
- Web UI: `python -m moodle_scraper.gui` then `curl http://127.0.0.1:8765/` — test API `POST /api/regen` returns 409 if busy, `GET /api/state?since=N` streams log.
- Real run (slow, ~20 min for ~212 tasks/224 files): `python -m moodle_scraper.main --live -o salida -v`.

## 13. Testing playbook (headless Chromium in CI)

- Synthetic nav: spin `ThreadingHTTPServer` with fake course/section HTML (charset `utf-8`) and assert `list_assigns_in_course` finds fallback sections + section hint propagates to `entry["tema"]`.
- Snapshot: empty course must return `[]` + `salida/_debug/curso_*.html`.
- Report: check `grade_percent` (`7,00 / 10,00`→70.0, `Sin nota`→None), XSS neutralisation (`<script>` escaped in `#rows`), href encoding (`%20%5B`), cursor `pointer` only on `#tbl th[data-k]`.
- Launch: `validate_url` rejects `ftp://`, `""`; `QueueHandler` never raises; `_launch_browser` with fake `FakePW.chromium.launch(channel=...)`.

## 14. Known data (last full run)

- 212 tasks / 224 files / 6 courses targeted (8 visited). `resumen.json` 46 graded. Largest file ~25 MB ZIP. No errors after last regen; `backup.log` is the audit trail. `salida/` was emptied to avoid out-of-disk in demo but private branch keeps full dump.

## 15. Extending safely

- **New Moodle centre:** add `--url` handling is already plumbbed; Spanish labels may move — add fallbacks before tightening regex.
- **New file types:** `parse_assign._find_files` keys off `introattachment`/`assignsubmission_file` — add new `kind` there and icon in `report._KIND_ICON`.
- **Anonymise further:** keep `aliases.json` empty, expand `strip_teacher_prefix` regex if teacher prefix forms change, never log `Cookie` header.
- **No `.exe`:** user chose auto-installable launchers over PyInstaller (heavy, 60–120 MB, SmartScreen/antivirus noise). If requested later, build on Windows with `pyinstaller --windowed` + Brave detection; do not bundle 656 MB Chromium.

## 16. Gotchas

- `wait_for_selector(timeout=0)` with comma selector deadlocks — fixed to explicit timeout + `get_by_text` checks; never use `timeout=0`.
- `rm -rf salida` before a demo deletes the PRIVATE dump — use `/tmp/out_*` for tests.
- `polyfilled` Playwright on CachyOS needs fallback build (`ubuntu24.04-x64`) — ignore the `BEWARE: OS not officially supported` warning.
- `salida/backup.log` is also written by web UI; tail it for real progress (`━━ Curso [i/n]`).
