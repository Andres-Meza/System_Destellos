from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-inseguro-cambiar")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

INSTALLED_APPS = [
  "django.contrib.admin",
  "django.contrib.auth",
  "django.contrib.contenttypes",
  "django.contrib.sessions",
  "django.contrib.messages",
  "django.contrib.staticfiles",
  "tienda",
  "cuentas",
  "panel",
]

MIDDLEWARE = [
  "django.middleware.security.SecurityMiddleware",
  "django.contrib.sessions.middleware.SessionMiddleware",
  "django.middleware.common.CommonMiddleware",
  "django.middleware.csrf.CsrfViewMiddleware",
  "django.contrib.auth.middleware.AuthenticationMiddleware",
  "django.contrib.messages.middleware.MessageMiddleware",
  "django.middleware.clickjacking.XFrameOptionsMiddleware",
  "cuentas.middleware.ClienteMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
  {
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
      "context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "tienda.context_processors.tienda_config",
      ],
    },
  },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
  "default": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": config("DB_NAME", default="destellos"),
    "USER": config("DB_USER", default="root"),
    "PASSWORD": config("DB_PASSWORD", default=""),
    "HOST": config("DB_HOST", default="127.0.0.1"),
    "PORT": config("DB_PORT", default="3306"),
    # Falla en 10 s con un mensaje claro si MySQL no responde (en vez de quedarse colgado)
    "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 10},
  }
}

AUTH_PASSWORD_VALIDATORS = [
  {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
  {
    "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    "OPTIONS": {"min_length": 10},
  },
  {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
  {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Autenticación del personal (modelo de usuario estándar de Django) ---
AUTHENTICATION_BACKENDS = ["cuentas.backends.UsuarioOCorreoBackend"]
LOGIN_URL = "panel_login"
LOGIN_REDIRECT_URL = "panel_inicio"
LOGOUT_REDIRECT_URL = "panel_login"
PANEL_SESION_SEGUNDOS = 60 * 60 * 8   # duración de la sesión del personal
PANEL_MAX_INTENTOS = 5                # intentos fallidos antes de bloquear
PANEL_BLOQUEO_SEGUNDOS = 60 * 15      # duración del bloqueo

# Cookies seguras: activas automáticamente cuando DEBUG=False (HTTPS).
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Imágenes de productos subidas desde el panel (se guardan dentro de static/img/productos/)
PRODUCTO_IMG_DIR = BASE_DIR / "static" / "img" / "productos"
PRODUCTO_IMG_MAX_BYTES = 2 * 1024 * 1024

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Sesión de clientes (tabla `clientes`)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7

# --- Carrito / compra ---
# La BD no maneja inventario, así que se usa un tope razonable por producto
# (se valida en el navegador Y en el servidor).
CARRITO_MAX_POR_PRODUCTO = 99
CARRITO_MAX_LINEAS = 50

# Registro de errores del servidor (visible en la consola de runserver)
LOGGING = {
  "version": 1,
  "disable_existing_loggers": False,
  "handlers": {"console": {"class": "logging.StreamHandler"}},
  "loggers": {"tienda": {"handlers": ["console"], "level": "INFO"}},
}

# Crea las tablas "managed=False" en la BD de pruebas (ver tienda/test_runner.py)
TEST_RUNNER = "tienda.test_runner.RunnerTablasExistentes"
