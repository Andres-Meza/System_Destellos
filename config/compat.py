"""
Compatibilidad Django 5.0 + Python 3.15.

Problema verificado: en Python 3.15, `copy(super())` (usado por
`django.template.context.BaseContext.__copy__` en Django 5.0.x) lanza
`AttributeError: 'super' object has no attribute 'dicts'`.
Django lo usa al renderizar etiquetas de inclusión, así que TODAS las pantallas
de /admin/ (listados y formularios) respondían 500, y también fallaban 13 pruebas
que usan el cliente de pruebas de Django.

Solución definitiva: pasar a Django 5.2 LTS o superior (requiere MariaDB >= 10.5
o MySQL 8). Mientras se use Django 5.0, este parche aplica la misma corrección
que incluyen las versiones nuevas. Solo actúa si detecta el fallo y se
desactiva solo en cuanto se actualiza Django.
"""
from copy import copy


def aplicar_parche_context():
  """Devuelve True si tuvo que aplicar el parche, False si no hacía falta."""
  from django.template.context import BaseContext, Context

  try:
    copy(Context({}))
    return False
  except AttributeError:
    pass

  def __copy__(self):
    duplicate = BaseContext()
    duplicate.__class__ = self.__class__
    duplicate.__dict__ = copy(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

  BaseContext.__copy__ = __copy__
  return True
