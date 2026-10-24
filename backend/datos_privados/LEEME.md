# Datos privados

Esta carpeta **no se sube a GitHub** (está en `.gitignore`). Aquí van los archivos con datos reales del equipo, por ejemplo `equipo.json` para crear las cuentas:

```bash
cp datos_iniciales/equipo.ejemplo.json datos_privados/equipo.json   # y pon a las personas reales
python manage.py cargar_equipo datos_privados/equipo.json            # muestra lo que haría
python manage.py cargar_equipo datos_privados/equipo.json --aplicar  # crea las cuentas
```
