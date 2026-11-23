@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [SocialVault] Preparando ambiente virtual...
py -3.11 -m venv .venv 2>nul
if errorlevel 1 py -3 -m venv .venv
if errorlevel 1 (
  echo Erro: instale Python 3.11 ou superior pelo site oficial python.org.
  pause
  exit /b 1
)
call .venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto failed
call .venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto failed
echo.
echo Pronto. Execute iniciar_windows.bat
pause
exit /b 0
:failed
echo Falha ao instalar dependencias. Verifique internet e Python.
pause
exit /b 1
