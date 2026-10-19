"""
Ajustes SOLO para pruebas locales rápidas con SQLite (no necesita MySQL):
    python manage.py test --settings=config.settings_test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_prueba.sqlite3",  # noqa: F405
    }
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # pruebas más rápidas
