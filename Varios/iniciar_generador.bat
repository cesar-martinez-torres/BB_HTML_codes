@echo off
setlocal

echo ===============================
echo Generador de Calendario HTML
echo ===============================

:: Verificar si el entorno ya existe
if not exist env (
    echo Creando entorno virtual...
    python -m venv env
) else (
    echo Entorno virtual ya existe.
)

echo Activando entorno virtual...
call env\Scripts\activate

echo Instalando dependencias necesarias...
pip install --upgrade pip >nul
pip install -r requirements.txt

echo Ejecutando la aplicación...
python generador_calendario.py

echo.
echo Aplicación finalizada. Pulsa cualquier tecla para cerrar...
pause >nul
