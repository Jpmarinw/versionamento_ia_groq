@echo off
:loop
cd /d "d:\jmarinho\Projetos\versionamento_ia_groq"
echo [%date% %time%] Iniciando API do AI Commit Reporter... >> api.log
uv run uvicorn api:app --host 0.0.0.0 --port 8000 >> api.log 2>&1

echo.
echo [ERRO] O servidor caiu! Tentando reiniciar automaticamente em 5 segundos...
echo [DICA] Para parar o servidor de vez, feche esta janela ou pressione Ctrl+C varias vezes.
timeout /t 5
goto loop
