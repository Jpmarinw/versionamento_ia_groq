@echo off
setlocal enabledelayedexpansion
echo [CONTROLE] Procurando processo da API na porta 8000...

set killed=0

:: Busca o PID do processo que esta ouvindo (LISTENING) na porta 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R /C:":8000 " ^| findstr LISTENING') do (
    if NOT "%%a"=="0" if NOT "%%a"=="4" (
        echo [OK] Finalizando processo da API (PID: %%a)
        taskkill /f /pid %%a /t >nul 2>&1
        set killed=1
    )
)

if !killed!==1 (
    echo [INFO] API encerrada com sucesso.
    echo [INFO] Aguardando liberacao da porta...
    timeout /t 2 >nul
) else (
    echo [INFO] Nenhum processo da API encontrado na porta 8000.
)
