@echo off
setlocal enabledelayedexpansion

:loop
cd /d "d:\jmarinho\Projetos\versionamento_ia_groq"
echo [%date% %time%] Iniciando API do AI Commit Reporter... >> api.log
uv run uvicorn api:app --host 0.0.0.0 --port 8000 >> api.log 2>&1
set exit_code=%errorlevel%

:: Se foi interrompido com Ctrl+C (exit code 3221225786 ou 1), não reinicia
if %exit_code%==3221225786 goto :manual_stop
if %exit_code%==1 goto :manual_stop
if %exit_code%==0 goto :manual_stop

echo.
echo [ERRO] O servidor caiu! (Exit code: %exit_code%)
echo [INFO] Tentando reiniciar automaticamente em 5 segundos...
echo [DICA] Para parar o servidor de vez, feche esta janela ou pressione Ctrl+C 2 vezes.
timeout /t 5
goto loop

:manual_stop
echo.
echo [INFO] Servidor parado manualmente pelo usuario.
echo [%date% %time%] Servidor encerrado >> api.log
exit /b 0
