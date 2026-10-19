"""
Validación y almacenamiento seguro de imágenes de productos.

- No se confía en el nombre ni en el Content-Type enviados por el navegador:
  se detecta el formato por los primeros bytes (PNG, JPEG, WebP).
- El archivo se guarda con un nombre aleatorio propio; el nombre original se descarta.
- SVG y cualquier otro formato se rechazan (el SVG puede contener scripts).
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

PREFIJO = "productos/"
NOMBRE_PROPIO = "producto-"


def detectar_extension(cabecera: bytes):
  if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
    return "png"
  if cabecera.startswith(b"\xff\xd8\xff"):
    return "jpg"
  if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
    return "webp"
  return None


def validar_imagen(archivo):
  """Devuelve la extensión real o lanza ValidationError."""
  maximo = settings.PRODUCTO_IMG_MAX_BYTES
  if archivo.size > maximo:
    raise ValidationError(f"La imagen supera el tamaño máximo de {maximo // (1024 * 1024)} MB.")
  archivo.seek(0)
  extension = detectar_extension(archivo.read(16))
  archivo.seek(0)
  if extension is None:
    raise ValidationError("Formato no permitido. Sube una imagen PNG, JPG o WebP válida.")
  return extension


def guardar_imagen(archivo):
  """Guarda el archivo ya validado y devuelve el valor para Producto.imagen."""
  extension = validar_imagen(archivo)
  carpeta = Path(settings.PRODUCTO_IMG_DIR)
  carpeta.mkdir(parents=True, exist_ok=True)
  nombre = f"{NOMBRE_PROPIO}{uuid.uuid4().hex[:12]}.{extension}"
  with open(carpeta / nombre, "wb") as destino:
    for trozo in archivo.chunks():
      destino.write(trozo)
  return PREFIJO + nombre


def borrar_si_es_propia(valor, otros_usos=False):
  """
  Elimina el archivo solo si lo subió el panel (productos/producto-*) y ningún otro
  producto lo usa. Las imágenes originales de la tienda (pack1.png, ...) nunca se borran.
  """
  if not valor or otros_usos:
    return
  if not (valor.startswith(PREFIJO + NOMBRE_PROPIO) and "/" not in valor[len(PREFIJO):] and ".." not in valor):
    return
  ruta = Path(settings.PRODUCTO_IMG_DIR) / valor[len(PREFIJO):]
  try:
    ruta.unlink()
  except FileNotFoundError:
    pass
