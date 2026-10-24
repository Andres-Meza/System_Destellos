import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from tienda.models import Cliente, DetallePedido, Pago, Pedido, Producto

from . import imagenes
from .forms import ESTADOS_PEDIDO, PedidoEstadoForm, ProductoForm, UsuarioCrearForm, UsuarioEditarForm
from .reglas import es_ultimo_superusuario_activo, etiqueta_rol

logger = logging.getLogger(__name__)
Usuario = get_user_model()
POR_PAGINA = 15


# ---------------------------------------------------------------------------
# Control de acceso (siempre en el servidor)
#   - Sin sesión            -> redirige al login del panel.
#   - Con sesión sin permiso -> 403 (página "Acceso denegado").
# ---------------------------------------------------------------------------
class PanelMixin(LoginRequiredMixin, PermissionRequiredMixin):
  """Exige cuenta activa del personal (is_staff) y, si se define, los permisos nativos."""

  permission_required = ()

  def has_permission(self):
    u = self.request.user
    return u.is_authenticated and u.is_active and u.is_staff and super().has_permission()


class SoloAdminMixin(PanelMixin):
  """Solo superusuarios activos (gestión de usuarios)."""

  def has_permission(self):
    return super().has_permission() and self.request.user.is_superuser


class PaginaMixin:
  """Contexto común: sección activa y título."""

  seccion = ""
  titulo = ""

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["seccion"] = self.seccion
    ctx["titulo"] = self.titulo
    return ctx


def _buscar(request):
  return request.GET.get("q", "").strip()[:100]


# ---------------------------------------------------------------------------
# Inicio / resumen
# ---------------------------------------------------------------------------
class InicioView(PaginaMixin, PanelMixin, TemplateView):
  template_name = "panel/inicio.html"
  seccion = "inicio"
  titulo = "Resumen"

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    u = self.request.user
    resumen = []
    if u.has_perm("tienda.view_producto"):
      resumen.append(("Productos", Producto.objects.count(), reverse("panel_productos")))
    if u.has_perm("tienda.view_pedido"):
      resumen.append(("Pedidos", Pedido.objects.count(), reverse("panel_pedidos")))
      resumen.append(
        ("Pedidos pendientes", Pedido.objects.filter(estado="Pendiente").count(),
         reverse("panel_pedidos") + "?estado=Pendiente")
      )
    if u.has_perm("tienda.view_cliente"):
      resumen.append(("Clientes", Cliente.objects.count(), reverse("panel_clientes")))
    if u.is_superuser:
      resumen.append(("Usuarios activos", Usuario.objects.filter(is_active=True).count(), reverse("panel_usuarios")))
    ctx["resumen"] = resumen
    ctx["rol"] = etiqueta_rol(u)
    return ctx


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------
class ProductoListView(PaginaMixin, PanelMixin, ListView):
  permission_required = "tienda.view_producto"
  template_name = "panel/producto_lista.html"
  context_object_name = "productos"
  paginate_by = POR_PAGINA
  seccion = "productos"
  titulo = "Productos"

  def get_queryset(self):
    qs = Producto.objects.all().order_by("-id_producto")
    q = _buscar(self.request)
    if q:
      qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    return qs

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["q"] = _buscar(self.request)
    return ctx


class ProductoCrearView(PaginaMixin, PanelMixin, CreateView):
  permission_required = "tienda.add_producto"
  model = Producto
  form_class = ProductoForm
  template_name = "panel/producto_form.html"
  success_url = reverse_lazy("panel_productos")
  seccion = "productos"
  titulo = "Nuevo producto"

  def form_valid(self, form):
    respuesta = super().form_valid(form)
    messages.success(self.request, f"Producto «{self.object.nombre}» creado.")
    return respuesta


class ProductoEditarView(PaginaMixin, PanelMixin, UpdateView):
  permission_required = "tienda.change_producto"
  model = Producto
  form_class = ProductoForm
  template_name = "panel/producto_form.html"
  success_url = reverse_lazy("panel_productos")
  seccion = "productos"
  titulo = "Editar producto"

  def form_valid(self, form):
    respuesta = super().form_valid(form)
    messages.success(self.request, f"Producto «{self.object.nombre}» actualizado.")
    return respuesta


class ProductoEliminarView(PaginaMixin, PanelMixin, DeleteView):
  permission_required = "tienda.delete_producto"
  model = Producto
  template_name = "panel/producto_eliminar.html"
  success_url = reverse_lazy("panel_productos")
  seccion = "productos"
  titulo = "Eliminar producto"

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["pedidos_asociados"] = DetallePedido.objects.filter(producto=self.object).count()
    return ctx

  def form_valid(self, form):
    producto = self.object
    # Protege la integridad: no se borra un producto que ya aparece en pedidos.
    if DetallePedido.objects.filter(producto=producto).exists():
      messages.error(
        self.request,
        "Este producto aparece en pedidos existentes y no se puede eliminar. "
        "Puedes editarlo o cambiar su precio.",
      )
      return redirect("panel_productos")
    imagen = producto.imagen
    try:
      with transaction.atomic():
        producto.delete()
    except IntegrityError:
      messages.error(self.request, "No se pudo eliminar: el producto tiene datos asociados.")
      return redirect("panel_productos")
    imagenes.borrar_si_es_propia(imagen, otros_usos=Producto.objects.filter(imagen=imagen).exists())
    messages.success(self.request, f"Producto «{producto.nombre}» eliminado.")
    return redirect(self.success_url)


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------
class PedidoListView(PaginaMixin, PanelMixin, ListView):
  permission_required = "tienda.view_pedido"
  template_name = "panel/pedido_lista.html"
  context_object_name = "pedidos"
  paginate_by = POR_PAGINA
  seccion = "pedidos"
  titulo = "Pedidos"

  def get_queryset(self):
    qs = Pedido.objects.select_related("cliente").order_by("-id_pedido")
    estado = self.request.GET.get("estado", "").strip()
    if estado:
      qs = qs.filter(estado=estado)
    q = _buscar(self.request)
    if q:
      filtro = Q(cliente__nombre__icontains=q) | Q(cliente__correo__icontains=q)
      if q.isdigit():
        filtro |= Q(pk=int(q))
      qs = qs.filter(filtro)
    return qs

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["q"] = _buscar(self.request)
    ctx["estado"] = self.request.GET.get("estado", "").strip()
    ctx["estados"] = ESTADOS_PEDIDO
    return ctx


class PedidoDetalleView(PaginaMixin, PanelMixin, TemplateView):
  permission_required = "tienda.view_pedido"
  template_name = "panel/pedido_detalle.html"
  seccion = "pedidos"
  titulo = "Detalle del pedido"

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    pedido = get_object_or_404(Pedido.objects.select_related("cliente"), pk=self.kwargs["pk"])
    detalles = pedido.detalles.select_related("producto")
    ctx["pedido"] = pedido
    ctx["lineas"] = [{"d": d, "subtotal": d.precio_unitario * d.cantidad} for d in detalles]
    ctx["pagos"] = Pago.objects.filter(pedido=pedido)
    ctx["form_estado"] = kwargs.get("form_estado") or PedidoEstadoForm(
      actual=pedido.estado, initial={"estado": pedido.estado}
    )
    ctx["puede_cambiar"] = self.request.user.has_perm("tienda.change_pedido")
    return ctx


class PedidoEstadoView(PanelMixin, View):
  """Cambia el estado de un pedido (solo POST, requiere tienda.change_pedido)."""

  permission_required = "tienda.change_pedido"

  def post(self, request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = PedidoEstadoForm(request.POST, actual=pedido.estado)
    if form.is_valid():
      pedido.estado = form.cleaned_data["estado"]
      pedido.save(update_fields=["estado"])
      messages.success(request, f"Pedido #{pedido.pk}: estado actualizado a «{pedido.estado}».")
    else:
      messages.error(request, "Estado no válido.")
    return redirect("panel_pedido_detalle", pk=pedido.pk)


# ---------------------------------------------------------------------------
# Clientes (solo consulta; la contraseña nunca se muestra)
# ---------------------------------------------------------------------------
class ClienteListView(PaginaMixin, PanelMixin, ListView):
  permission_required = "tienda.view_cliente"
  template_name = "panel/cliente_lista.html"
  context_object_name = "clientes"
  paginate_by = POR_PAGINA
  seccion = "clientes"
  titulo = "Clientes"

  def get_queryset(self):
    qs = Cliente.objects.annotate(num_pedidos=Count("pedidos")).order_by("-id_cliente")
    q = _buscar(self.request)
    if q:
      qs = qs.filter(Q(nombre__icontains=q) | Q(correo__icontains=q))
    return qs

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["q"] = _buscar(self.request)
    return ctx


# ---------------------------------------------------------------------------
# Gestión de usuarios (exclusiva del administrador)
# ---------------------------------------------------------------------------
class UsuarioListView(PaginaMixin, SoloAdminMixin, ListView):
  template_name = "panel/usuario_lista.html"
  context_object_name = "usuarios"
  paginate_by = POR_PAGINA
  seccion = "usuarios"
  titulo = "Gestión de usuarios"

  def get_queryset(self):
    qs = Usuario.objects.prefetch_related("groups").order_by("-date_joined")
    q = _buscar(self.request)
    if q:
      qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    return qs

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["q"] = _buscar(self.request)
    for u in ctx["usuarios"]:
      u.rol_texto = etiqueta_rol(u)
    return ctx


class UsuarioCrearView(PaginaMixin, SoloAdminMixin, CreateView):
  model = Usuario
  form_class = UsuarioCrearForm
  template_name = "panel/usuario_form.html"
  success_url = reverse_lazy("panel_usuarios")
  seccion = "usuarios"
  titulo = "Nuevo usuario"

  def form_valid(self, form):
    with transaction.atomic():
      self.object = form.save()
    messages.success(self.request, f"Usuario «{self.object.username}» creado.")
    return redirect(self.success_url)


class UsuarioEditarView(PaginaMixin, SoloAdminMixin, UpdateView):
  model = Usuario
  form_class = UsuarioEditarForm
  template_name = "panel/usuario_form.html"
  success_url = reverse_lazy("panel_usuarios")
  seccion = "usuarios"
  titulo = "Editar usuario"

  def get_form_kwargs(self):
    kwargs = super().get_form_kwargs()
    kwargs["actor"] = self.request.user
    return kwargs

  def form_valid(self, form):
    with transaction.atomic():
      self.object = form.save()
    messages.success(self.request, f"Usuario «{self.object.username}» actualizado.")
    return redirect(self.success_url)

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    ctx["edicion"] = True
    return ctx


class UsuarioContrasenaView(PaginaMixin, SoloAdminMixin, TemplateView):
  """El administrador define una contraseña nueva (se guarda con hash seguro)."""

  template_name = "panel/usuario_contrasena.html"
  seccion = "usuarios"
  titulo = "Restablecer contraseña"

  def _usuario(self):
    return get_object_or_404(Usuario, pk=self.kwargs["pk"])

  def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)
    usuario = self._usuario()
    ctx["objetivo"] = usuario
    ctx["form"] = kwargs.get("form") or AdminPasswordChangeForm(usuario)
    return ctx

  def post(self, request, *args, **kwargs):
    usuario = self._usuario()
    form = AdminPasswordChangeForm(usuario, request.POST)
    if form.is_valid():
      form.save()
      if usuario.pk == request.user.pk:
        update_session_auth_hash(request, usuario)  # no cierra tu propia sesión
      messages.success(request, f"Contraseña de «{usuario.username}» actualizada.")
      return redirect("panel_usuarios")
    return self.render_to_response(self.get_context_data(form=form))


class UsuarioEstadoView(SoloAdminMixin, View):
  """Activa o desactiva una cuenta (solo POST). Nunca deja el sistema sin administrador."""

  def post(self, request, pk):
    with transaction.atomic():
      usuario = get_object_or_404(Usuario.objects.select_for_update(), pk=pk)
      if usuario.is_active:
        if usuario.pk == request.user.pk:
          messages.error(request, "No puedes desactivar tu propia cuenta.")
          return redirect("panel_usuarios")
        if es_ultimo_superusuario_activo(usuario):
          messages.error(request, "No se puede desactivar al último administrador activo.")
          return redirect("panel_usuarios")
        usuario.is_active = False
        mensaje = f"Cuenta «{usuario.username}» desactivada."
      else:
        usuario.is_active = True
        mensaje = f"Cuenta «{usuario.username}» activada."
      usuario.save(update_fields=["is_active"])
    messages.success(request, mensaje)
    return redirect("panel_usuarios")
