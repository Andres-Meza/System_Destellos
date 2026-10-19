from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

Usuario = get_user_model()


class UsuarioOCorreoBackend(ModelBackend):
  """
  Autentica con nombre de usuario O correo electrónico, siempre con las
  funciones seguras de Django (check_password) y respetando is_active.

  Reglas para evitar ambigüedades:
    1. Primero se busca por nombre de usuario (sin distinguir mayúsculas).
    2. Solo si el texto contiene "@" y no coincide con ningún usuario, se busca
       por correo.
    3. Si el correo (o el usuario) coincide con MÁS de una cuenta, se rechaza el
       acceso: nunca se adivina a qué cuenta pertenece.
  El formulario de creación de usuarios impide correos duplicados.
  """

  def authenticate(self, request, username=None, password=None, **kwargs):
    if username is None:
      username = kwargs.get(Usuario.USERNAME_FIELD)
    if not username or password is None:
      return None

    usuario = self._buscar(username.strip())
    if usuario is None:
      # Gasta el mismo tiempo que una verificación real (evita revelar si existe).
      Usuario().set_password(password)
      return None
    if usuario.check_password(password) and self.user_can_authenticate(usuario):
      return usuario
    return None

  @staticmethod
  def _buscar(identificador):
    manager = Usuario._default_manager
    coincidencias = list(manager.filter(username__iexact=identificador)[:2])
    if not coincidencias and "@" in identificador:
      coincidencias = list(manager.filter(email__iexact=identificador)[:2])
    return coincidencias[0] if len(coincidencias) == 1 else None
