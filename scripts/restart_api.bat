@echo off
cd /d "%~dp0"
echo [RESTART] Reiniciando a API de forma automatica...

:: Primeiro para a API
call stop_api.bat

:: Agora inicia novamente via VBS (escondido)
echo [START] Iniciando servidor em segundo plano...
start "" "run_hidden.vbs"

echo [OK] A API foi reiniciada e ja estara pronta em alguns segundos.
timeout /t 3
