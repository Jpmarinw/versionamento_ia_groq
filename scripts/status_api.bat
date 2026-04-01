@echo off
echo [STATUS] Verificando status da API...

:: Verifica se a porta 8000 esta em uso
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R /C:":8000 " ^| findstr LISTENING') do (
    if NOT "%%a"=="0" if NOT "%%a"=="4" (
        echo [OK] API esta rodando (PID: %%a)
        echo.
        echo [INFO] Logs recentes:
        echo ========================================
        powershell -Command "Get-Content ..\api.log -Tail 10"
        echo ========================================
        exit /b 0
    )
)

echo [INFO] API NAO esta rodando na porta 8000.
echo.
echo [DICA] Use 'start_api.bat' para iniciar ou 'restart_api.bat' para reiniciar.
