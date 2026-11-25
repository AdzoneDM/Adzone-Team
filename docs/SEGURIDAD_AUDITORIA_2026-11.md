# Auditoría de seguridad de Adzone Team: informe (25/11/2026)

Documento interno y confidencial: describe puntos débiles. Compartirlo solo con Dirección y Tecnología.

## 1. Alcance y método

- **Qué se revisó:**
  - Backend (Django + DRF), frontend (React), base de datos y consultas.
  - Inicio de sesión, sesiones y verificación en dos pasos.
  - Usuarios, roles y permisos, y las APIs de los 18 módulos.
  - Carga y descarga de archivos, el portal de clientes y las cabeceras HTTP.
  - TLS, contenedores Docker, puertos expuestos y firewall.
  - Respaldos, dependencias y variables de entorno.
- **Cómo se revisó:**
  - Lectura del código y pruebas controladas con el cliente de pruebas de Django sobre bases desechables, con varias cuentas y perfiles: se cambiaron identificadores en URL y API, se usaron enlaces directos a archivos y se forzaron intentos de entrada.
  - Revisión del servidor de producción en **solo lectura**.
  - No se hicieron pruebas destructivas en producción.
- **Respaldo antes de cada despliegue:** la base se respalda en `/root/respaldos-previos/` y la imagen anterior queda guardada para volver atrás.

## 2. Resumen

- **Riesgo general antes:** medio-alto. La plataforma ya tenía buenos controles:
  - control de acceso por objeto en el backend;
  - archivos privados fuera del sitio público, servidos solo con sesión y permiso;
  - verificación en dos pasos y cierre por inactividad;
  - cookies seguras, HSTS, CSRF y contenedor sin privilegios.
- **Lo grave estaba en dos puntos:**
  - **Contraseñas:** la contraseña base común no era obligatorio cambiarla y el límite de intentos se podía saltar.
  - **Permisos ocultos:** algunos accesos se daban por pertenecer a un área o a un grupo, fuera del sistema de permisos, y se escapaban del control contra la escalada.
- **Después de la 12.67:** todos los hallazgos críticos, altos y medios de la aplicación están corregidos y probados. Quedan pendientes algunos puntos del **servidor compartido**, que necesitan tu decisión (sección 6).
- **No se encontró:**
  - SQL Injection (no hay SQL a mano).
  - XSS explotable (React y sin HTML de usuarios).
  - Acceso a datos ajenos cambiando el identificador de un registro (IDOR clásico).
  - Archivos privados accesibles sin sesión, secretos en el código ni trazas de error expuestas.

## 3. Inventario de hallazgos y estado

| # | Riesgo | Hallazgo | Estado |
|---|---|---|---|
| A1 | **Alto** | Todas las cuentas nuevas reciben la misma contraseña base. Cambiarla era opcional: la API seguía funcionando con ella. | **Corregido.** Con la contraseña base, el servidor bloquea todo salvo cambiarla, y la app muestra una pantalla obligatoria. |
| A2 | **Alto** | El límite de 12 intentos por cuenta se saltaba mandando `user_id` con un `username` distinto en cada intento. | **Corregido.** El límite usa la cuenta ya resuelta (por id, correo o usuario). |
| A3 | **Alto** | Finanzas se daba a **cualquiera con un puesto en el área «Administración»**, sin ningún permiso. Incluía el costo por hora de cada persona. | **Corregido.** Ahora es el permiso «Finanzas». Nadie perdió acceso: quien lo tenía por su área quedó con una excepción visible. |
| A4 | **Alto** | Escalada: Coordinación, Almacén y Call Center se daban por grupo o por área, fuera del control «no puedes dar lo que no tienes». Quien crea usuarios podía otorgarlos. | **Corregido.** Son permisos («Coordinación de producción», «Almacén», «Campañas de Call Center») y el control contra la escalada los cubre. |
| M1 | Medio | Sin bloqueo de la cuenta: con IPs distintas se podían probar contraseñas sin freno. | **Corregido.** 10 fallos en 15 min, desde cualquier IP, bloquean esa cuenta 15 min y avisan a la persona y a quien audita. |
| M2 | Medio | No quedaba registro de entradas, fallos ni salidas. La IP guardada era la del proxy, no la real. | **Corregido.** Nueva bitácora de accesos con IP real, navegador, dispositivo, resultado y riesgo. |
| M3 | Medio | No había forma de ver ni cerrar las sesiones abiertas. | **Corregido.** Mi cuenta → Sesiones abiertas (cerrar una o todas las demás). Quien administra personas también puede hacerlo por API. |
| M4 | Medio | La bitácora no registraba altas y cambios de cuentas, cambios de perfiles, cambios y restablecimientos de contraseña, exportaciones, descargas de documentos ni accesos denegados. | **Corregido.** Todo eso queda registrado. Un restablecimiento de contraseña además avisa a la persona. |
| M5 | Medio | Quien pedía una OT veía la mano de obra por área, de la que se deduce el costo por hora de una persona. | **Corregido.** Solo la ven Finanzas, Coordinación y quien tiene «Salarios»; el resto ve el total y el margen. |
| M6 | Medio | Toda la empresa (incluido el Call Center) podía descargar la lista completa de clientes con RNC, teléfonos, correos y notas internas. | **Corregido.** Esos datos solo los ven quien gestiona, vende o factura; el resto ve el nombre. |
| M7 | Medio | Archivos de órdenes («ARTE», que el cliente descarga desde el portal) se aceptaban solo por la extensión. | **Corregido.** Se revisa el contenido real (sin ejecutables, PDF e imágenes verdaderos) y los ZIP pasan la revisión del chat (antivirus). |
| M8 | Medio | Las descargas de documentos del expediente, de Finanzas y del portal no quedaban registradas. | **Corregido.** |
| B1 | Bajo | El login aceptaba formularios de otros sitios (CSRF en el inicio de sesión). | **Corregido.** CSRF exigido en la entrada, en la clave general y en el segundo paso. |
| B2 | Bajo | Contraseñas con PBKDF2. | **Corregido.** Ahora Argon2id; las existentes se convierten solas al entrar. |
| B3 | Bajo | La app no tenía Content-Security-Policy. | **Corregido.** CSP estricta (solo scripts propios) y Permissions-Policy. Probado en el navegador sin bloqueos. |
| B4 | Bajo | La clave general del equipo solo tenía el límite amplio por IP. | **Corregido.** Límite propio de 20 por minuto y cada fallo queda registrado. |
| B5 | Bajo | Los límites de intentos vivían en la memoria de cada proceso (se multiplicaban por 3). | **Corregido.** Caché compartida en la base. |
| B6 | Bajo | Archivos de tareas eliminadas seguían descargables, y una referencia se podía borrar con la tarea en la papelera. | **Corregido.** |
| B7 | Bajo | Se podían añadir filas falsas a la bitácora desde /admin. | **Corregido.** |
| B8 | Bajo | Nombre de archivo sin escapar en la cabecera de los videos; el tipo de un archivo de OT salía del navegador. | **Corregido.** |
| B9 | Bajo | Compensación variable y beneficios de todos los puestos visibles para todos. | **Corregido.** Los ven quien ocupa el puesto, Talento, Salarios y Dirección. |
| B10 | Bajo | Un supervisor con solo «Ver a su equipo» veía las anotaciones internas del expediente. | **Corregido.** Exige «Expediente y planes de mejora». |
| B11 | Bajo | Ninguna lista de la API está paginada (permite sacar muchos datos de una vez). | Pendiente. Las listas ya están limitadas por permisos; paginar exige cambiar pantallas. |
| B12 | Bajo | El enlace del portal de clientes lleva el token en la URL (queda en los registros del servidor web). | Pendiente. El token es de 256 bits, vence y se puede revocar. |

## 4. Controles nuevos (12.67)

- **Bitácora de accesos** (Talento → Accesos, con el permiso «Ver la auditoría»). Registra:
  - entradas y contraseñas o códigos equivocados;
  - bloqueos de cuenta y entradas poco habituales;
  - sesiones cerradas a distancia y accesos denegados (403);
  - IPs no permitidas y cambios de contraseña.
  - Muestra el resumen de las últimas 24 horas y las IPs con más fallos.
- **Evaluación de riesgo al entrar.** Un cambio de IP **nunca bloquea por sí solo**. Suman puntos:
  - dispositivo nuevo;
  - red nunca usada por esa persona;
  - otra sesión desde otra red en los últimos 30 minutos;
  - hora poco habitual (23:00 a 5:00);
  - 3 o más fallos en la última hora.
  - Con 2 puntos o más se avisa a la persona y a quien audita; no se bloquea.
- **Bloqueo por cuenta:** 10 contraseñas equivocadas en 15 minutos, desde cualquier IP, bloquean esa cuenta 15 minutos.
- **IPs permitidas para cuentas de empresa** (Dirección, Personas y accesos, Talento, Salarios, Configuración) y para /admin. Variable `IPS_ADMIN` del servidor, desactivada por defecto. Ejemplo: `IPS_ADMIN=200.215.233.0/24` deja entrar esas cuentas solo desde la oficina.
- **Sesiones abiertas** por persona, con dispositivo, IP y hora de entrada, para cerrarlas a distancia.
- **Retención:** la bitácora de cambios y la de accesos no se pueden editar ni borrar desde la plataforma ni desde /admin. Se propone conservarlas al menos 2 años.

## 5. Pruebas de verificación

Cada corrección tiene su prueba automática (`apps/core/tests_auditoria_seguridad.py`, 15 pruebas), y la suite completa pasa. Lo comprobado:
- 10 fallos desde 10 IPs bloquean la cuenta, y la contraseña correcta no entra durante el bloqueo.
- El `user_id` y el correo cuentan para la misma cuenta.
- Con la contraseña base solo se puede cambiarla.
- Entrada, fallo y salida quedan con IP y dispositivo.
- Cerrar una sesión a distancia deja fuera a ese dispositivo, y nadie cierra sesiones ajenas por esa vía.
- Una entrada poco habitual avisa sin bloquear.
- La bitácora de accesos exige permiso, y el 403 queda registrado.
- Las IPs permitidas funcionan.
- El área «Administración» ya no da Finanzas.
- Los clientes salen sin datos de contacto para quien no gestiona.
- Se rechazan un PDF falso, un ejecutable disfrazado y un script.
- La CSP está presente.
- La bitácora no admite filas inventadas, y el restablecimiento de contraseña queda registrado y avisa.

En el navegador, la app compilada funciona con la CSP sin bloqueos en Inicio, Mis tareas, Mi equipo, Validar, Asistencia, Talento, Mi cuenta y Órdenes.

## 6. Servidor e infraestructura

**Bien:**
- HTTPS obligatorio; TLS 1.0 y 1.1 rechazados.
- HSTS, `X-Frame-Options`, `nosniff` y `Referrer-Policy` activos.
- Rutas como `/.env` o `/.git` devuelven la app, no archivos.
- El contenedor web corre sin privilegios, sin capacidades y con sistema de archivos de solo lectura.
- La base de datos de Adzone Team no está expuesta.
- Respaldos accesibles solo para root.
- Firewall con política de denegar e Imunify360 y fail2ban (13 jaulas) activos.
- Los puertos 3306 (MariaDB), 21 (FTP) y 110 (POP3) están **bloqueados** para internet. Solo la IP de la oficina pasa (regla explícita), y el registro del firewall muestra intentos externos a 3306 bloqueados.

**Pendiente (necesita tu decisión: afecta al servidor compartido):**

| Riesgo | Hallazgo | Recomendación |
|---|---|---|
| **Urgente** | El certificado HTTPS de kpi.adzone.marketing **vence el 30/11/2026** y no se ha renovado solo. | Plesk → kpi.adzone.marketing → SSL/TLS (SSL It!) → renovar. Revisar que la renovación automática esté activa. |
| Alto | **n8n (puerto 5678) abierto a internet directamente.** Docker se salta el firewall, y se llega a n8n sin pasar por el dominio. | Dejarlo solo en 127.0.0.1 (el dominio automation.adzone.marketing sigue funcionando). Preparado: una regla `DOCKER-USER` instantánea y el cambio en `/opt/n8n/docker-compose.yml` (`127.0.0.1:5678:5678`), con un reinicio de n8n de segundos. **No se aplicó**: el sistema pidió tu autorización por tratarse de otro proyecto del servidor. |
| Medio | SSH permite entrar como root y con contraseña (fail2ban lo mitiga). | Usar solo claves (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`). **Antes**, confirmar que todos los que entran (PuTTY) tienen clave; si no, quedan fuera. |
| Medio | FTP y POP3 sin cifrar habilitados (aunque bloqueados desde internet). | Si nadie los usa, desactivarlos en Plesk. |
| Bajo | 8 actualizaciones del sistema pendientes (docker-ce, entre otras). | Aplicarlas en una ventana de mantenimiento. |
| Bajo | La cabecera `X-Powered-By: PleskLin` revela la plataforma. | Ocultarla en la configuración de nginx de Plesk. |
| Recomendado | La verificación en dos pasos es opcional (`DOS_PASOS_OBLIGATORIA=0`). | Ponerla en `1`: será obligatoria para Gerencia, Administración y Tecnología. |
| Recomendado | `IPS_ADMIN` vacío. | Si Dirección y Tecnología trabajan desde la oficina, poner la red de la oficina. |

## 7. Recomendaciones siguientes

1. Renovar el certificado (urgente) y cerrar el puerto directo de n8n.
2. Activar la verificación en dos pasos obligatoria y, si aplica, `IPS_ADMIN`.
3. Revisar en Accesos y permisos las excepciones marcadas «Lo tenía por su área antes de la 12.67».
4. Rotar la clave general del equipo cuando alguien deje la empresa.
5. Paginar las listas grandes de la API (B11) y sacar el token del portal de los registros del servidor web (B12).
6. Repetir esta auditoría cada 6 meses y después de cambios grandes.
