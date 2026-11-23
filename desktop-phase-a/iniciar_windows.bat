@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute instalar_windows.bat primeiro.
 pause
 exit /b 1
)
set /p URL=Cole o link do TikTok: 
echo.
echo 1 - Video MP4
 echo 2 - Audio MP3 (precisa de FFmpeg)
set /p MODO=Escolha 1 ou 2: 
if "%MODO%"=="2" (
  ".venv\Scripts\python.exe" -m socialvault download "%URL%" --mode mp3
) else (
  ".venv\Scripts\python.exe" -m socialvault download "%URL%" --mode mp4
)
echo.
pause
