# Conector de Cashflow

| Archivo | Qué tiene |
| --- | --- |
| `rutas.py` | Método y ruta de cada operación. **Lo primero que se revisa** con la documentación de cashflow.do/dev. |
| `mapeo.py` | Cómo se arma cada envío (cliente, cotización, factura) y cómo se leen las respuestas (id, número, NCF, saldo, pagos). |
| `cliente.py` | Llamadas HTTP con la API key (cabecera configurable) y el simulador del modo de prueba. |
| `servicios.py` | Lo que hace la plataforma: vincular clientes por RNC, enviar cotizaciones, emitir facturas, traer pagos. |

Configuración en `backend/.env`:

```
CASHFLOW_API_URL=https://api.cashflow.do      # la base que diga la documentación
CASHFLOW_API_KEY=…                            # la clave de la app «API-CASHFLOW» (APP-1001). Nunca en GitHub.
CASHFLOW_AUTH_HEADER=Authorization            # o X-API-Key, según la documentación
CASHFLOW_AUTH_PREFIX=Bearer                   # vacío si la clave va sola
```

Sin `CASHFLOW_API_KEY` todo funciona en **modo de prueba**: el simulador responde como Cashflow (ids SIM-…, e-CF de ejemplo) y no envía nada.

Para comprobar: **Administración → Integraciones → Probar conexión**, o `python manage.py sincronizar_cashflow --probar`.
