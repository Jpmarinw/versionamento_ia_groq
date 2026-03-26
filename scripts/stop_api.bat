@echo off
echo [CONTROLE] Procurando processo da API na porta 8000...

:: Busca o PID do processo que esta usando a porta 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    echo [OK] Finalizando processo PID: %%a
    taskkill /f /pid %%a /t
)

echo [INFO] API encerrada com sucesso.
timeout /t 2
