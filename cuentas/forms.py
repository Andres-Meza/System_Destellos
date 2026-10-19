from django import forms


class LoginForm(forms.Form):
  """Inicio de sesión de CLIENTES de la tienda (tabla `clientes`)."""

  correo = forms.EmailField(
    label="Correo electrónico",
    widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com", "id": "email"}),
  )
  contrasena = forms.CharField(
    label="Contraseña",
    widget=forms.PasswordInput(attrs={"placeholder": "••••••••", "id": "password"}),
  )


class PanelLoginForm(forms.Form):
  """Inicio de sesión del PERSONAL (usuarios de Django) para el panel privado."""

  usuario = forms.CharField(
    label="Usuario o correo electrónico",
    max_length=150,
    widget=forms.TextInput(
      attrs={
        "id": "usuario",
        "autocomplete": "username",
        "autocapitalize": "none",
        "spellcheck": "false",
        "autofocus": True,
      }
    ),
  )
  contrasena = forms.CharField(
    label="Contraseña",
    strip=False,
    widget=forms.PasswordInput(attrs={"id": "password", "autocomplete": "current-password"}),
  )
