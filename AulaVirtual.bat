@echo off
REM Doble clic: abre la interfaz sin ventana de consola
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0AulaVirtual.ps1" %*
