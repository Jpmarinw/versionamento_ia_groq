@echo off
echo [LOG MANAGER] Gerenciando arquivos de log...

set LOG_FILE=..\api.log
set MAX_LINES=1000
set BACKUP_DIR=..\logs_backup
set lines=0

if not exist "%LOG_FILE%" (
    echo [INFO] Arquivo de log nao encontrado.
    goto :showsize
)

for /f "delims=" %%a in ('powershell -Command "(Get-Content '%LOG_FILE%').Count"') do set lines=%%a
if "%lines%"=="" set lines=0

echo [INFO] Linhas atuais: %lines%

if %lines% GTR %MAX_LINES% (
    echo [ALERTA] Log ultrapassou %MAX_LINES% linhas!
    if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
    set timestamp=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
    set timestamp=%timestamp: =0%
    copy "%LOG_FILE%" "%BACKUP_DIR%\api_%timestamp%.log" >nul
    echo [OK] Backup criado.
    powershell -Command "Get-Content '%LOG_FILE%' -Tail %MAX_LINES% | Set-Content '%LOG_FILE%.tmp'"
    move /y "%LOG_FILE%.tmp" "%LOG_FILE%" >nul
    echo [OK] Log truncado para %MAX_LINES% linhas.
) else (
    echo [OK] Log dentro do limite.
)

:showsize
for %%a in ("%LOG_FILE%") do echo [INFO] Tamanho: %%~za bytes
