from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group

from tienda.models import Producto

from . import imagenes
from .reglas import ROL_ADMIN, ROL_STAFF, ROLES, es_ultimo_superusuario_activo, rol_de

Usuario = get_user_model()

ESTADOS_PEDIDO = ("Pendiente", "En proceso", "Enviado", "Entregado", "Cancelado")


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------
class ProductoForm(forms.ModelForm):
  imagen_archivo = forms.FileField(
    label="Imagen",
    required=False,
    help_text="PNG, JPG o WebP de hasta 2 MB.",
    widget=forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
  )
  quitar_imagen = forms.BooleanField(label="Quitar la imagen actual", required=False)

  class Meta:
    model = Producto
    fields = ("nombre", "descripcion", "precio")
    widgets = {"descripcion": forms.Textarea(attrs={"rows": 5})}
    labels = {"nombre": "Nombre", "descripcion": "Descripción", "precio": "Precio"}

  def clean_nombre(self):
    nombre = self.cleaned_data["nombre"].strip()
    if not nombre:
      raise forms.ValidationError("Escribe el nombre del producto.")
    return nombre

  def clean_precio(self):
    precio = self.cleaned_data["precio"]
    if precio <= 0:
      raise forms.ValidationError("El precio debe ser mayor que cero.")
    return precio

  def clean_imagen_archivo(self):
    archivo = self.cleaned_data.get("imagen_archivo")
    if archivo:
      imagenes.validar_imagen(archivo)
    return archivo

  def save(self, commit=True):
    producto = super().save(commit=False)
    anterior = (
      Producto.objects.filter(pk=producto.pk).values_list("imagen", flat=True).first()
      if producto.pk
      else None
    )
    nueva = None
    archivo = self.cleaned_data.get("imagen_archivo")
    if archivo:
      nueva = imagenes.guardar_imagen(archivo)
      producto.imagen = nueva
    elif self.cleaned_data.get("quitar_imagen"):
      producto.imagen = None
    if not commit:
      return producto
    try:
      producto.save()
    except Exception:
      imagenes.borrar_si_es_propia(nueva)
      raise
    if anterior and anterior != producto.imagen:
      en_uso = Producto.objects.filter(imagen=anterior).exists()
      imagenes.borrar_si_es_propia(anterior, otros_usos=en_uso)
    return producto


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------
class PedidoEstadoForm(forms.Form):
  estado = forms.ChoiceField(label="Estado del pedido")

  def __init__(self, *args, actual=None, **kwargs):
    super().__init__(*args, **kwargs)
    opciones = list(ESTADOS_PEDIDO)
    if actual and actual not in opciones:
      opciones.insert(0, actual)  # conserva un estado ya guardado en la BD
    self.fields["estado"].choices = [(o, o) for o in opciones]


# ---------------------------------------------------------------------------
# Usuarios (solo administrador)
# ---------------------------------------------------------------------------
class _CamposRol(forms.Form):
  """Campos de rol y grupos compartidos por crear/editar."""

  rol = forms.ChoiceField(label="Rol", choices=ROLES, initial=ROL_STAFF)
  grupos = forms.ModelMultipleChoiceField(
    label="Módulos autorizados (grupos)",
    queryset=Group.objects.none(),
    required=False,
    widget=forms.CheckboxSelectMultiple,
    help_text="Solo se aplican al usuario administrativo. El administrador tiene acceso total.",
  )

  def _preparar_campos_rol(self):
    self.fields["grupos"].queryset = Group.objects.order_by("name")


def _validar_correo_unico(form, excluir_pk=None):
  correo = form.cleaned_data.get("email", "").strip()
  if not correo:
    raise forms.ValidationError("El correo electrónico es obligatorio.")
  existentes = Usuario.objects.filter(email__iexact=correo)
  if excluir_pk:
    existentes = existentes.exclude(pk=excluir_pk)
  if existentes.exists():
    raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
  return correo


class UsuarioCrearForm(UserCreationForm, _CamposRol):
  """
  Crea usuarios del personal. Los privilegios (is_staff / is_superuser) los fija
  el servidor según `rol`: nunca se leen campos como is_superuser del POST.
  """

  class Meta(UserCreationForm.Meta):
    model = Usuario
    fields = ("username", "first_name", "last_name", "email")
    labels = {
      "username": "Nombre de usuario",
      "first_name": "Nombre",
      "last_name": "Apellido",
      "email": "Correo electrónico",
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._preparar_campos_rol()
    for nombre in ("first_name", "last_name", "email"):
      self.fields[nombre].required = True
    self.fields["password1"].label = "Contraseña"
    self.fields["password2"].label = "Confirmar contraseña"

  def clean_email(self):
    return _validar_correo_unico(self)

  def save(self, commit=True):
    usuario = super().save(commit=False)  # aplica set_password (hash seguro)
    usuario.is_staff = True
    usuario.is_superuser = self.cleaned_data["rol"] == ROL_ADMIN
    usuario.is_active = True
    if commit:
      usuario.save()
      self._asignar_grupos(usuario)
    return usuario

  def _asignar_grupos(self, usuario):
    grupos = self.cleaned_data["grupos"] if self.cleaned_data["rol"] == ROL_STAFF else []
    usuario.groups.set(grupos)


class UsuarioEditarForm(forms.ModelForm, _CamposRol):
  class Meta:
    model = Usuario
    fields = ("first_name", "last_name", "email")
    labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Correo electrónico"}

  def __init__(self, *args, actor, **kwargs):
    super().__init__(*args, **kwargs)
    self.actor = actor
    self._preparar_campos_rol()
    for nombre in ("first_name", "last_name", "email"):
      self.fields[nombre].required = True
    if self.instance.pk:
      self.fields["rol"].initial = rol_de(self.instance)
      self.fields["grupos"].initial = self.instance.groups.all()

  def clean_email(self):
    return _validar_correo_unico(self, excluir_pk=self.instance.pk)

  def clean(self):
    datos = super().clean()
    if datos.get("rol") == ROL_STAFF and self.instance.is_superuser:
      if self.instance.pk == self.actor.pk:
        raise forms.ValidationError("No puedes quitarte a ti mismo el rol de administrador.")
      if es_ultimo_superusuario_activo(self.instance):
        raise forms.ValidationError("No se puede degradar al último administrador activo.")
    return datos

  def save(self, commit=True):
    usuario = super().save(commit=False)
    usuario.is_staff = True
    usuario.is_superuser = self.cleaned_data["rol"] == ROL_ADMIN
    if commit:
      usuario.save()
      grupos = self.cleaned_data["grupos"] if self.cleaned_data["rol"] == ROL_STAFF else []
      usuario.groups.set(grupos)
    return usuario
