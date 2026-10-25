@echo off
rem Abre o aplicativo de vibrometria (duplo clique). Aceita uma sessao .vibro.json como argumento.
cd /d "%~dp0Code"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Ambiente virtual nao encontrado em "%~dp0.venv".
    echo Crie-o e instale as dependencias:  python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m vibroapp %*
