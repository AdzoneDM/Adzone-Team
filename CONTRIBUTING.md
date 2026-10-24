# Cómo trabajar en Adzone Team

## Ramas

- `main` es lo que está (o va a estar) en el servidor. No se trabaja directo en `main`.
- Cada cambio va en su propia rama, con un nombre corto que diga qué hace:
  - `funcion/tablero-por-departamento`
  - `arreglo/aviso-duplicado`
  - `docs/guia-supervisores`

```bash
git checkout main && git pull
git checkout -b funcion/mi-cambio
# … cambios …
git add -A && git commit -m "Tablero: filtrar por departamento"
git push -u origin funcion/mi-cambio
```

Luego abre un **Pull Request** hacia `main` en GitHub.

## Antes de pedir revisión

1. `cd backend && python manage.py test apps` pasa.
2. Si cambiaste un modelo: `python manage.py makemigrations` y sube la migración nueva.
3. `cd frontend && npm run lint && npm run build` pasa.
4. Probaste la pantalla en la PC **y** en el celular (en el navegador: herramientas → vista de celular, 390 px).

GitHub corre los puntos 1 a 3 solo (pestaña *Checks* del Pull Request). Si sale en rojo, no se une.

## Reglas de la casa

- **Fácil de usar, de aprender y de recordar; que prevenga errores.** Textos en español claro, sin jerga técnica en pantalla.
- **Mínimo privilegio:** cada persona ve y cambia solo lo que le toca. Toda regla de permisos va en el backend (`apps/desempeno/permisos.py`), no solo en la pantalla.
- **Nunca** subir datos reales: base de datos, fotos, `.env`, contraseñas o listas del equipo (`backend/datos_privados/`).
- Un Pull Request = un cambio. Mejor varios pequeños que uno enorme.
- Commits en español, en presente: «Agrega…», «Corrige…».

## Dónde va cada cosa

| Quiero… | Archivo |
| --- | --- |
| Cambiar quién puede hacer qué | `backend/apps/desempeno/permisos.py` |
| Cambiar cómo se calcula el puntaje | `backend/apps/desempeno/puntaje.py` |
| Agregar un aviso | `backend/apps/desempeno/servicios.py` |
| Una pantalla nueva | `frontend/src/features/<área>/` y su ruta en `frontend/src/app/App.jsx` |
| Una pieza visual común | `frontend/src/components/ui.jsx` |
