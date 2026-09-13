<#
.SYNOPSIS
  Lanzador auto-instalable (Windows) — sin consola si lo abres con AulaVirtual.bat
  Doble clic instala Python/venv/deps la primera vez y abre la interfaz web.
#>
param(
  [int]$Port = 8765,
  [string]$Out = "salida"
)
$ErrorActionPreference = "Stop"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Dir

function Find-Python {
  foreach ($c in @("py -3", "python", "python3", "py")) {
    $parts = $c.Split(" ")
    try {
      & $parts[0] @($parts | Select-Object -Skip 1) --version 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) { return $c }
    } catch {}
  }
  return $null
}

function MsgBox($msg, $title="Aula Virtual") {
  try { Add-Type -AssemblyName System.Windows.Forms | Out-Null; [System.Windows.Forms.MessageBox]::Show($msg, $title) | Out-Null } catch { Write-Host $msg }
}

$py = Find-Python
if (-not $py) {
  MsgBox "No encontré Python. Instálalo desde https://www.python.org/downloads/ (marca 'Add to PATH') y vuelve a hacer doble clic."
  exit 1
}
$pyParts = $py.Split(" ")

# 1) venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "Creando entorno .venv..."
  & $pyParts[0] @($pyParts | Select-Object -Skip 1) -m venv .venv
  if ($LASTEXITCODE -ne 0) { MsgBox "No pude crear .venv. Revisa que Python esté bien instalado."; exit 1 }
}
$venvPy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { $venvPy = ".\.venv\Scripts\python" }

# 2) deps (solo si faltan o requirements cambió)
$needInstall = $true
if (Test-Path ".venv\installed.txt") {
  $a = (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash
  $b = (Get-Content ".venv\installed.txt" -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($a -eq $b) {
    try { & $venvPy -c "import playwright" 2>$null; if ($LASTEXITCODE -eq 0) { $needInstall = $false } } catch {}
  }
}
if ($needInstall) {
  Write-Host "Instalando dependencias (solo la primera vez)..."
  & $venvPy -m pip install --upgrade pip
  & $venvPy -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { MsgBox "Falló pip install. Revisa tu conexión."; exit 1 }
  (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash | Set-Content ".venv\installed.txt"
}

# 3) ¿Hace falta descargar Chromium? Si tienes Brave/Chrome, nos lo ahorramos.
$hasBrave = $false
$bravePaths = @(
  "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe",
  "${env:ProgramFiles(x86)}\BraveSoftware\Brave-Browser\Application\brave.exe",
  "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe"
)
foreach ($p in $bravePaths) { if (Test-Path $p) { $hasBrave = $true; break } }
if (-not $hasBrave) {
  try { Get-Command brave -ErrorAction Stop | Out-Null; $hasBrave = $true } catch {}
  try { Get-Command brave-browser -ErrorAction Stop | Out-Null; $hasBrave = $true } catch {}
}
if (-not $hasBrave) {
  Write-Host "Descargando Chromium (solo primera vez, puede tardar)..."
  & $venvPy -m playwright install chromium
  if ($LASTEXITCODE -ne 0) { Write-Host "Aviso: playwright install falló, intentaré usar tu navegador igual." }
} else {
  Write-Host "Brave/Chrome detectado: no descargo Chromium."
}

# 4) Abrir interfaz
Write-Host "Abriendo interfaz en http://127.0.0.1:$Port ..."
Start-Process $venvPy -ArgumentList "-m","moodle_scraper.gui","--port",$Port,"-o",$Out -WindowStyle Hidden

Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:$Port/"
Write-Host "Si no se abrió el navegador, entra manualmente a http://127.0.0.1:$Port/"
