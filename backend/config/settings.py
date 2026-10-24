"""
Configuración de Adzone Team (tareas, KPIs y reconocimiento).

Todo lo que cambia entre la computadora de desarrollo y el servidor se lee de variables de
entorno (o del archivo backend/.env). Ver .env.example.

- En desarrollo no hace falta nada: sin DJANGO_SECRET_KEY arranca en modo desarrollo.
- En el servidor: DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS y, si se usa MySQL/MariaDB, DB_*.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env(ruta):
    """Lee un .env sencillo (CLAVE=valor) sin dependencias extra. No pisa variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, valor = linea.split('=', 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / '.env')


def env(nombre, defecto=''):
    return os.environ.get(nombre, defecto)


def env_lista(nombre, defecto=''):
    return [v.strip() for v in env(nombre, defecto).replace(',', ' ').split() if v.strip()]


# Sin clave propia = desarrollo. En el servidor siempre se define DJANGO_SECRET_KEY.
_CLAVE = env('DJANGO_SECRET_KEY')
DEBUG = env('DJANGO_DEBUG', '0' if _CLAVE else '1') == '1'
SECRET_KEY = _CLAVE or 'solo-para-desarrollo-local-no-usar-en-servidor'
if not DEBUG and not _CLAVE:
    raise RuntimeError('Falta DJANGO_SECRET_KEY en el servidor (ver .env.example).')

ALLOWED_HOSTS = env_lista('DJANGO_ALLOWED_HOSTS', 'localhost 127.0.0.1')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.core',
    'apps.kpis',
    'apps.organizacion',
    'apps.desempeno',
    'corsheaders',
    'rest_framework',
    'django_filters',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de datos: SQLite por defecto; MySQL/MariaDB (Plesk) o PostgreSQL con DB_ENGINE.
# ---------------------------------------------------------------------------
DB_ENGINE = env('DB_ENGINE', 'sqlite')
if DB_ENGINE == 'mysql':
    try:  # PyMySQL no necesita compilar nada en el servidor
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'), 'USER': env('DB_USER'), 'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', 'localhost'), 'PORT': env('DB_PORT', '3306'),
        'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
    }}
elif DB_ENGINE == 'postgresql':
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'), 'USER': env('DB_USER'), 'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', 'localhost'), 'PORT': env('DB_PORT', '5432'),
    }}
else:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': env('DB_NAME') or BASE_DIR / 'db.sqlite3',
    }}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# República Dominicana: las fechas de entrega y "hoy" se cuentan en hora local.
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Santo_Domingo'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_THROTTLE_RATES': {'login': '10/min'},
}

# La sesión dura 7 días si se marca «Recordarme»; si no, hasta cerrar el navegador.
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# En producción el frontend lo sirve el mismo Django (mismo dominio): no hace falta CORS.
# En desarrollo Vite usa un proxy, así que tampoco. Se deja por si se separan los dominios.
CORS_ALLOWED_ORIGINS = env_lista('CORS_ORIGINS', 'http://localhost:5173 http://127.0.0.1:5173')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_lista('CSRF_ORIGINS', 'http://localhost:5173 http://127.0.0.1:5173') + \
    env_lista('EXTRA_CSRF_ORIGINS')

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env('DJANGO_SSL_REDIRECT', '1') == '1'
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# Archivos
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# La app web ya compilada (npm run build) se sirve desde aquí, en el mismo dominio que la API.
FRONTEND_DIST = Path(env('FRONTEND_DIST', str(BASE_DIR.parent / 'frontend' / 'dist')))
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
WHITENOISE_INDEX_FILE = False
WHITENOISE_MAX_AGE = 60 * 60

# Evidencias: NUNCA se publican en /media. Se descargan por la API, que revisa quién puede verlas.
MEDIA_ROOT = Path(env('MEDIA_ROOT', str(BASE_DIR / 'media')))
MEDIA_URL = '/media-privada/'
EVIDENCIA_MAX_MB = int(env('EVIDENCIA_MAX_MB', '10'))
EVIDENCIA_MAX_ARCHIVOS = 6
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {'adzone': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}
