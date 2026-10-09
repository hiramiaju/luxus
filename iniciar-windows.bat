@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Primero sigue README.md para instalar dependencias y crear usuario.
 pause
 exit /b 1
)
.venv\Scripts\python.exe app.py
pause
