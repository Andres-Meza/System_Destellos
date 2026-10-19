"""Reglas de negocio de roles y usuarios (sin vistas ni formularios)."""
from django.contrib.auth import get_user_model

Usuario = get_user_model()

ROL_ADMIN = "admin"
ROL_STAFF = "staff"
ROLES = (
  (ROL_ADMIN, "Administrador (acceso total y gestión de usuarios)"),
  (ROL_STAFF, "Usuario administrativo (solo los módulos de sus grupos)"),
)


def rol_de(usuario):
  return ROL_ADMIN if usuario.is_superuser else ROL_STAFF


def etiqueta_rol(usuario):
  if usuario.is_superuser:
    return "Administrador"
  grupos = ", ".join(usuario.groups.order_by("name").values_list("name", flat=True))
  return grupos or "Usuario administrativo (sin módulos asignados)"


def es_ultimo_superusuario_activo(usuario):
  """True si `usuario` es el único superusuario activo (no se puede desactivar ni degradar)."""
  if not (usuario.is_superuser and usuario.is_active):
    return False
  return not Usuario.objects.filter(is_superuser=True, is_active=True).exclude(pk=usuario.pk).exists()
