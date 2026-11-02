@echo off
REM Crea AdzoneAgente.exe (un solo archivo, sin consola) para instalar en las computadoras de ADZONE.
REM Requiere Python 3.10+ para Windows instalado en la PC donde se construye.
python -m pip install --upgrade pip pyinstaller pystray pillow
python -m PyInstaller --onefile --noconsole --name AdzoneAgente adzone_agente.py
echo.
echo Listo: dist\AdzoneAgente.exe
echo Copialo a cada PC y pon un acceso directo en shell:startup para que arranque con Windows.
pause
