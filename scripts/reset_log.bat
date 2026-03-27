@echo off
echo [LOG RESET] Limpando o arquivo de log...

set LOG_FILE=..\api.log

if not exist "%LOG_FILE%" (
    echo [INFO] Arquivo de log nao encontrado.
    exit /b 0
)

:: Mostra tamanho atual
for %%a in ("%LOG_FILE%") do echo [INFO] Tamanho atual: %%~za bytes

:: Reseta o log
type nul > "%LOG_FILE%"

echo [OK] Log resetado com sucesso!
for %%a in ("%LOG_FILE%") do echo [INFO] Novo tamanho: %%~za bytes
