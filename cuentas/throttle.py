"""
Limitador sencillo de intentos de inicio de sesión (sin dependencias nuevas).
Se usa en el login del personal (ámbito "panel") y en el de clientes ("cliente"):
cada ámbito lleva sus propios contadores.

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


AMBITO_PANEL = "panel"
AMBITO_CLIENTE = "cliente"


def _claves(request, usuario, ambito):
  ip = request.META.get("REMOTE_ADDR", "") or "?"
  huella = hashlib.sha256(usuario.strip().lower().encode()).hexdigest()[:32]
  return f"login:{ambito}:ip:{ip}", f"login:{ambito}:ipuser:{ip}:{huella}"


def bloqueado(request, usuario, ambito=AMBITO_PANEL):
  k_ip, k_usuario = _claves(request, usuario, ambito)
  return (cache.get(k_ip, 0) >= MAX_POR_IP) or (cache.get(k_usuario, 0) >= MAX_POR_USUARIO)


def registrar_fallo(request, usuario, ambito=AMBITO_PANEL):
  for clave in _claves(request, usuario, ambito):
    cache.add(clave, 0, BLOQUEO)
    try:
      cache.incr(clave)
    except ValueError:
      cache.set(clave, 1, BLOQUEO)


def limpiar(request, usuario, ambito=AMBITO_PANEL):
  for clave in _claves(request, usuario, ambito):
    cache.delete(clave)
