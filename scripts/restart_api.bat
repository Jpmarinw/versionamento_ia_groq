@echo off
cd /d "%~dp0"
echo [RESTART] Reiniciando a API de forma automatica...

:: Gerencia o log antes de reiniciar
call manage_log.bat

:: Primeiro para a API
call stop_api.bat

:: Aguarda 2 segundos para garantir que a porta foi liberada
ping 127.0.0.1 -n 3 >nul

:: Agora inicia novamente via VBS (escondido)
echo [START] Iniciando servidor em segundo plano...
start "" "run_hidden.vbs"

echo [OK] A API foi reiniciada e ja estara pronta em alguns segundos.