from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from tienda.models import Cliente

from . import throttle
from .forms import LoginForm, PanelLoginForm


def _es_hash_django(valor):
  try:
    identify_hasher(valor)
    return True
  except ValueError:
    return False


def _verificar(cliente, clave):
  """
  Acepta contraseñas ya hasheadas con Django y, de forma transitoria, las
  contraseñas en texto plano que hoy tiene la tabla (clave_demo_1, ...).
  Si coincide en texto plano, se re-guarda hasheada automáticamente.
  """
  guardada = cliente.contrasena
  if _es_hash_django(guardada):
    return check_password(clave, guardada)
  if constant_time_compare(guardada, clave):
    cliente.contrasena = make_password(clave)
    cliente.save(update_fields=["contrasena"])
    return True
  return False


def _destino_seguro(request):
  """Devuelve ?next= solo si apunta a este mismo sitio (evita redirecciones abiertas)."""
  destino = request.POST.get("next") or request.GET.get("next") or ""
  if destino and url_has_allowed_host_and_scheme(
    destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
  ):
    return destino
  return ""


def login_view(request):
  siguiente = _destino_seguro(request)
  if request.cliente:
    return redirect(siguiente or "productos")

  form = LoginForm(request.POST or None)
  status = 200
  if request.method == "POST" and form.is_valid():
    correo = form.cleaned_data["correo"]
    clave = form.cleaned_data["contrasena"]
    if throttle.bloqueado(request, correo, throttle.AMBITO_CLIENTE):
      messages.error(request, "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo.")
      status = 429
    else:
      cliente = Cliente.objects.filter(correo__iexact=correo).first()
      if cliente and _verificar(cliente, clave):
        throttle.limpiar(request, correo, throttle.AMBITO_CLIENTE)
        request.session.cycle_key()
        request.session["id_cliente"] = cliente.pk
        messages.success(request, f"¡Bienvenido, {cliente.nombre}!")
        return redirect(siguiente or "productos")
      if cliente is None:
        make_password(clave)  # gasta el mismo tiempo que una verificación real (no revela si el correo existe)
      throttle.registrar_fallo(request, correo, throttle.AMBITO_CLIENTE)
      messages.error(request, "Correo o contraseña incorrectos.")
  return render(request, "cuentas/login.html", {"form": form, "next": siguiente}, status=status)


@require_POST
def logout_view(request):
  request.session.flush()
  return redirect("inicio")


# ---------------------------------------------------------------------------
# PERSONAL (usuarios de Django): acceso al panel privado
# ---------------------------------------------------------------------------
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


def panel_login(request):
  """
  Login del personal con authenticate() + login() de Django.
  - Mensaje de error genérico (no revela si el usuario existe ni si está inactivo).
  - Limita intentos por IP y por usuario.
  - Solo acepta cuentas activas con is_staff.
  """
  siguiente = _destino_seguro(request)
  if request.user.is_authenticated and request.user.is_staff:
    return redirect(siguiente or "panel_inicio")

  form = PanelLoginForm(request.POST or None)
  status = 200
  if request.method == "POST" and form.is_valid():
    identificador = form.cleaned_data["usuario"]
    if throttle.bloqueado(request, identificador):
      form.add_error(None, "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo.")
      status = 429
    else:
      usuario = authenticate(
        request, username=identificador, password=form.cleaned_data["contrasena"]
      )
      if usuario is not None and usuario.is_staff:
        throttle.limpiar(request, identificador)
        login(request, usuario)  # rota la clave de sesión
        request.session.set_expiry(getattr(settings, "PANEL_SESION_SEGUNDOS", 8 * 3600))
        messages.success(request, f"Bienvenido, {usuario.get_short_name() or usuario.get_username()}.")
        return redirect(siguiente or "panel_inicio")
      throttle.registrar_fallo(request, identificador)
      form.add_error(None, MENSAJE_CREDENCIALES)
  return render(request, "cuentas/panel_login.html", {"form": form, "next": siguiente}, status=status)


@require_POST
def panel_logout(request):
  """Cierre de sesión solo por POST (con CSRF): invalida la sesión en el servidor."""
  logout(request)
  messages.success(request, "Cerraste sesión correctamente.")
  return redirect("panel_login")
