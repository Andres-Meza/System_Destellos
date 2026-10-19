from django.urls import path

from . import views

urlpatterns = [
  # Clientes de la tienda
  path("login/", views.login_view, name="login"),
  path("logout/", views.logout_view, name="logout"),
  # Personal (panel privado). No existe ninguna ruta pública de registro.
  path("panel/ingresar/", views.panel_login, name="panel_login"),
  path("panel/salir/", views.panel_logout, name="panel_logout"),
]
