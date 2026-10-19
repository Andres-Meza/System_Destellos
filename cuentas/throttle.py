"""
Limitador sencillo de intentos de inicio de sesión (sin dependencias nuevas).

Usa la caché de Django. Con LocMemCache (valor por defecto) el conteo es por
proceso: suficiente en desarrollo. En producción con varios procesos configura
una caché compartida (Redis/Memcached) en CACHES.
Detrás de un proxy inverso, REMOTE_ADDR debe ser la IP real del cliente.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache

MAX_POR_USUARIO = getattr(settings, "PANEL_MAX_INTENTOS", 5)
MAX_POR_IP = MAX_POR_USUARIO * 4
BLOQUEO = getattr(settings, "PANEL_BLOQUEO_SEGUNDOS", 15 * 60)


def _claves(request, usuario):
  ip = request.META.get("REMOTE_ADDR", "") or "?"
  huella = hashlib.sha256(usuario.strip().lower().encode()).hexdigest()[:32]
  return f"login:ip:{ip}", f"login:ipuser:{ip}:{huella}"


def bloqueado(request, usuario):
  k_ip, k_usuario = _claves(request, usuario)
  return (cache.get(k_ip, 0) >= MAX_POR_IP) or (cache.get(k_usuario, 0) >= MAX_POR_USUARIO)


def registrar_fallo(request, usuario):
  for clave in _claves(request, usuario):
    cache.add(clave, 0, BLOQUEO)
    try:
      cache.incr(clave)
    except ValueError:
      cache.set(clave, 1, BLOQUEO)


def limpiar(request, usuario):
  for clave in _claves(request, usuario):
    cache.delete(clave)
