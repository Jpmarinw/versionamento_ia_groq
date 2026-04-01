@echo off
cd /d "%~dp0"
echo [RESTART] Reiniciando a API...

:: Para a API
call stop_api.bat

:: Aguarda liberacao da porta
ping 127.0.0.1 -n 3 >nul

:: Inicia em segundo plano
echo [START] Iniciando servidor...
start "" "run_hidden.vbs"

echo [OK] API reiniciada.
