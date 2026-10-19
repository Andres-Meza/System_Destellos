"""
Roles basados en grupos y permisos NATIVOS de Django (no hay sistema paralelo).

- Administrador          -> cuenta con is_superuser (todos los permisos + gestión de usuarios).
- Usuario administrativo -> is_staff + los grupos que el administrador le asigne.

Los grupos solo se CREAN si no existen: si el administrador ajusta sus permisos
desde /admin/, una nueva migración no los sobrescribe. Un usuario sin grupos no
tiene acceso a ningún módulo.
"""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import DEFAULT_DB_ALIAS

# nombre del grupo -> permisos (codename) sobre la app `tienda`
GRUPOS_BASE = {
  "Gestor de productos": [
    "view_producto", "add_producto", "change_producto", "delete_producto",
  ],
  "Gestor de pedidos": [
    "view_pedido", "change_pedido", "view_detallepedido", "view_pago", "view_cliente",
  ],
  "Consulta": [
    "view_producto", "view_pedido", "view_detallepedido", "view_pago", "view_cliente",
  ],
}


def crear_grupos_base(sender=None, using=DEFAULT_DB_ALIAS, apps=global_apps, **kwargs):
  try:
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
  except LookupError:
    return

  # Garantiza que los permisos de `tienda` existen (idempotente).
  create_permissions(
    global_apps.get_app_config("tienda"), verbosity=0, using=using, apps=apps
  )

  for nombre, codenames in GRUPOS_BASE.items():
    grupo, creado = Group.objects.using(using).get_or_create(name=nombre)
    if not creado:
      continue
    permisos = Permission.objects.using(using).filter(
      content_type__app_label="tienda", codename__in=codenames
    )
    grupo.permissions.set(permisos)
