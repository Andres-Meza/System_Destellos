from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CuentasConfig(AppConfig):
  name = "cuentas"

  def ready(self):
    from config.compat import aplicar_parche_context

    from .grupos import crear_grupos_base

    aplicar_parche_context()
    # Crea los grupos base (sin usuarios) cuando ya existen los permisos de `tienda`.
    post_migrate.connect(
      crear_grupos_base, sender=self, dispatch_uid="cuentas.crear_grupos_base"
    )
