from copy import copy

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.template import Context
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from tienda.models import Cliente

Usuario = get_user_model()
CLAVE = "Clave-Segura-2026!"


def crear_usuario(username, *, superuser=False, staff=True, active=True, email=None, clave=CLAVE):
  return Usuario.objects.create_user(
    username,
    email or f"{username}@ejemplo.com",
    clave,
    is_staff=staff,
    is_superuser=superuser,
    is_active=active,
  )


class LoginPanelTests(TestCase):
  def setUp(self):
    cache.clear()
    self.admin = crear_usuario("admin1", superuser=True)
    self.url = reverse("panel_login")

  def ingresar(self, usuario="admin1", clave=CLAVE, client=None, extra=""):
    return (client or self.client).post(self.url + extra, {"usuario": usuario, "contrasena": clave})

  def test_la_pagina_de_login_es_publica_y_trae_csrf(self):
    r = self.client.get(self.url)
    self.assertEqual(r.status_code, 200)
    self.assertContains(r, "csrfmiddlewaretoken")
    self.assertContains(r, 'name="usuario"')
    self.assertContains(r, 'name="contrasena"')

  def test_1_el_administrador_puede_iniciar_sesion(self):
    r = self.ingresar()
    self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)
    self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)
    self.assertEqual(self.client.get(reverse("panel_inicio")).status_code, 200)

  def test_se_puede_ingresar_con_correo(self):
    r = self.ingresar(usuario="ADMIN1@ejemplo.com")
    self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)

  def test_correo_repetido_no_autentica_a_nadie(self):
    Usuario.objects.filter(pk=self.admin.pk).update(email="mismo@ejemplo.com")
    crear_usuario("otro", email="mismo@ejemplo.com")
    r = self.ingresar(usuario="mismo@ejemplo.com")
    self.assertEqual(r.status_code, 200)
    self.assertNotIn("_auth_user_id", self.client.session)

  def test_2_usuario_inexistente_no_entra(self):
    r = self.ingresar(usuario="fantasma")
    self.assertContains(r, "Usuario o contraseña incorrectos.")
    self.assertNotIn("_auth_user_id", self.client.session)

  def test_3_contrasena_incorrecta_no_entra_y_el_mensaje_no_revela_si_el_usuario_existe(self):
    r_mala = self.ingresar(clave="otra-cosa-123")
    r_fantasma = self.ingresar(usuario="fantasma", clave="otra-cosa-123")
    self.assertNotIn("_auth_user_id", self.client.session)
    self.assertContains(r_mala, "Usuario o contraseña incorrectos.")
    msg = lambda r: r.context["form"].non_field_errors().as_text()
    self.assertEqual(msg(r_mala), msg(r_fantasma))

  def test_9_usuario_desactivado_no_inicia_sesion_y_su_sesion_abierta_deja_de_valer(self):
    u = crear_usuario("temporal", superuser=True)
    c = Client()
    self.assertEqual(self.ingresar("temporal", client=c).status_code, 302)
    self.assertEqual(c.get(reverse("panel_inicio")).status_code, 200)
    Usuario.objects.filter(pk=u.pk).update(is_active=False)
    r = c.get(reverse("panel_inicio"))
    self.assertEqual(r.status_code, 302)  # la sesión ya no es válida
    r = self.ingresar("temporal", client=Client())
    self.assertContains(r, "Usuario o contraseña incorrectos.")

  def test_cuenta_sin_is_staff_no_entra_al_panel(self):
    crear_usuario("cliente_web", staff=False)
    r = self.ingresar("cliente_web", client=Client())
    self.assertContains(r, "Usuario o contraseña incorrectos.")

  def test_next_interno_se_respeta_y_externo_se_ignora(self):
    r = self.ingresar(extra="?next=/panel/productos/")
    self.assertRedirects(r, "/panel/productos/", fetch_redirect_response=False)
    self.client.post(reverse("panel_logout"))
    r = self.ingresar(extra="?next=https://malo.example/")
    self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)

  def test_bloqueo_tras_varios_intentos_fallidos(self):
    for _ in range(5):
      self.ingresar(clave="mala-mala-123")
    r = self.ingresar()  # incluso con la clave correcta
    self.assertEqual(r.status_code, 429)
    self.assertContains(r, "Demasiados intentos", status_code=429)
    self.assertNotIn("_auth_user_id", self.client.session)

  def test_10_logout_solo_por_post_invalida_la_sesion_y_confirma(self):
    self.ingresar()
    self.assertEqual(self.client.get(reverse("panel_logout")).status_code, 405)
    self.assertIn("_auth_user_id", self.client.session)
    r = self.client.post(reverse("panel_logout"), follow=True)
    self.assertRedirects(r, reverse("panel_login"))
    self.assertContains(r, "Cerraste sesión correctamente.")
    self.assertNotIn("_auth_user_id", self.client.session)
    self.assertEqual(self.client.get(reverse("panel_inicio")).status_code, 302)

  def test_14_login_y_logout_exigen_csrf(self):
    c = Client(enforce_csrf_checks=True)
    r = c.post(self.url, {"usuario": "admin1", "contrasena": CLAVE})
    self.assertEqual(r.status_code, 403)
    c.force_login(self.admin)
    self.assertEqual(c.post(reverse("panel_logout")).status_code, 403)

  def test_contrasena_guardada_con_hash_seguro(self):
    identify_hasher(self.admin.password)  # lanza ValueError si no es un hash de Django
    self.assertNotIn(CLAVE, self.admin.password)

  def test_no_existe_ruta_publica_de_registro(self):
    for ruta in ("/registro/", "/registrar/", "/signup/", "/panel/registro/", "/panel/usuarios/nuevo/"):
      r = Client().get(ruta)
      self.assertIn(r.status_code, (302, 404), ruta)
      if r.status_code == 302:
        self.assertIn("/panel/ingresar/", r["Location"])

  def test_grupos_base_existen_pero_nadie_los_tiene_asignado(self):
    nombres = set(Group.objects.values_list("name", flat=True))
    self.assertTrue({"Gestor de productos", "Gestor de pedidos", "Consulta"} <= nombres)
    productos = Group.objects.get(name="Gestor de productos")
    self.assertTrue(productos.permissions.filter(codename="add_producto").exists())
    self.assertFalse(productos.permissions.filter(codename="add_pedido").exists())
    self.assertEqual(productos.user_set.count(), 0)

  def test_la_copia_de_contextos_de_plantilla_funciona_en_esta_version_de_python(self):
    # Regresión: Django 5.0 + Python 3.15 fallaba aquí (ver config/compat.py).
    copia = copy(Context({"a": 1}))
    self.assertEqual(copia["a"], 1)


@override_settings(PANEL_MAX_INTENTOS=2)
class LimiteConfigurableTests(TestCase):
  def test_el_limite_se_lee_de_settings(self):
    from cuentas import throttle
    self.assertGreaterEqual(throttle.MAX_POR_USUARIO, 1)


class LoginClienteBloqueoTests(TestCase):
  """El login de clientes (/login/) limita intentos como el del personal, con contadores propios."""

  def setUp(self):
    cache.clear()
    self.cliente = Cliente.objects.create(nombre="Ana", correo="ana@x.com", contrasena="clave123")
    self.url = reverse("login")

  def tearDown(self):
    cache.clear()  # los contadores viven en la caché del proceso: no contaminar otras pruebas

  def ingresar(self, clave, correo="ana@x.com"):
    return self.client.post(self.url, {"correo": correo, "contrasena": clave})

  def test_bloqueo_tras_varios_intentos_fallidos_incluso_con_la_clave_correcta(self):
    for _ in range(5):
      self.assertEqual(self.ingresar("mala").status_code, 200)
    r = self.ingresar("clave123")
    self.assertEqual(r.status_code, 429)
    self.assertContains(r, "Demasiados intentos", status_code=429)
    self.assertNotIn("id_cliente", self.client.session)

  def test_correo_inexistente_tambien_cuenta_y_el_mensaje_es_el_mismo(self):
    r = self.ingresar("x", correo="nadie@x.com")
    self.assertContains(r, "Correo o contraseña incorrectos")
    for _ in range(4):
      self.ingresar("x", correo="nadie@x.com")
    self.assertEqual(self.ingresar("x", correo="nadie@x.com").status_code, 429)

  def test_acertar_limpia_los_fallos(self):
    for _ in range(4):
      self.ingresar("mala")
    self.assertEqual(self.ingresar("clave123").status_code, 302)
    self.client.post(reverse("logout"))
    for _ in range(4):
      self.ingresar("mala")
    self.assertEqual(self.ingresar("clave123").status_code, 302)

  def test_los_fallos_de_clientes_no_bloquean_al_personal(self):
    crear_usuario("admin1", superuser=True)
    for _ in range(5):
      self.ingresar("mala")
    r = self.client.post(reverse("panel_login"), {"usuario": "admin1", "contrasena": CLAVE})
    self.assertEqual(r.status_code, 302)
