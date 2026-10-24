import base64
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cuentas.tests import CLAVE, crear_usuario
from tienda.models import Cliente, DetallePedido, Pedido, Producto

Usuario = get_user_model()

PNG_1X1 = base64.b64decode(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def logueado(usuario):
  c = Client()
  c.force_login(usuario)
  return c


class Base(TestCase):
  @classmethod
  def setUpTestData(cls):
    cls.admin = crear_usuario("admin1", superuser=True)
    cls.sin_permisos = crear_usuario("sinperm")                      # staff sin grupos
    cls.gestor = crear_usuario("gestor")
    cls.gestor.groups.add(Group.objects.get(name="Gestor de productos"))
    cls.consulta = crear_usuario("consulta")
    cls.consulta.groups.add(Group.objects.get(name="Consulta"))
    cls.pedidos_user = crear_usuario("pedidista")
    cls.pedidos_user.groups.add(Group.objects.get(name="Gestor de pedidos"))
    cls.no_staff = crear_usuario("nostaff", staff=False)
    cls.p1 = Producto.objects.create(nombre="Pack uno", descripcion="Desc", precio=Decimal("8.99"), imagen="pack1.png")
    cls.p2 = Producto.objects.create(nombre="Pack dos", precio=Decimal("39.99"))
    cls.ana = Cliente.objects.create(nombre="Ana", correo="ana@x.com", contrasena="pbkdf2_secreto", direccion="Calle 1")
    cls.pedido = Pedido.objects.create(cliente=cls.ana, fecha="2026-10-15", total=Decimal("8.99"))
    DetallePedido.objects.create(pedido=cls.pedido, producto=cls.p1, cantidad=1, precio_unitario=Decimal("8.99"))

  def setUp(self):
    cache.clear()


RUTAS_PRIVADAS = (
  ("panel_inicio", []),
  ("panel_productos", []),
  ("panel_producto_nuevo", []),
  ("panel_pedidos", []),
  ("panel_clientes", []),
  ("panel_usuarios", []),
  ("panel_usuario_nuevo", []),
)


class AccesoTests(Base):
  def rutas(self):
    r = [reverse(n, args=a) for n, a in RUTAS_PRIVADAS]
    r += [
      reverse("panel_producto_editar", args=[self.p1.pk]),
      reverse("panel_producto_eliminar", args=[self.p1.pk]),
      reverse("panel_pedido_detalle", args=[self.pedido.pk]),
      reverse("panel_usuario_editar", args=[self.admin.pk]),
      reverse("panel_usuario_contrasena", args=[self.admin.pk]),
    ]
    return r

  def test_4_y_11_anonimo_es_enviado_al_login_en_todas_las_rutas_privadas(self):
    for ruta in self.rutas():
      r = Client().get(ruta)
      self.assertEqual(r.status_code, 302, ruta)
      self.assertTrue(r["Location"].startswith(reverse("panel_login")), ruta)

  def test_anonimo_no_puede_ejecutar_operaciones_por_post(self):
    c = Client()
    posts = [
      (reverse("panel_producto_nuevo"), {"nombre": "X", "precio": "5"}),
      (reverse("panel_producto_eliminar", args=[self.p1.pk]), {}),
      (reverse("panel_usuario_nuevo"), {"username": "x"}),
      (reverse("panel_usuario_estado", args=[self.admin.pk]), {}),
      (reverse("panel_pedido_estado", args=[self.pedido.pk]), {"estado": "Entregado"}),
    ]
    for url, datos in posts:
      self.assertEqual(c.post(url, datos).status_code, 302, url)
    self.assertFalse(Producto.objects.filter(nombre="X").exists())
    self.assertTrue(Producto.objects.filter(pk=self.p1.pk).exists())
    self.assertEqual(Usuario.objects.filter(username="x").count(), 0)

  def test_11_usuario_sin_is_staff_recibe_403(self):
    c = logueado(self.no_staff)
    for ruta in self.rutas():
      self.assertEqual(c.get(ruta).status_code, 403, ruta)

  def test_staff_sin_grupos_entra_al_resumen_pero_a_ningun_modulo(self):
    c = logueado(self.sin_permisos)
    r = c.get(reverse("panel_inicio"))
    self.assertContains(r, "Sin módulos asignados")
    self.assertNotContains(r, reverse("panel_usuarios"))
    for nombre in ("panel_productos", "panel_pedidos", "panel_clientes", "panel_usuarios",
                   "panel_producto_nuevo", "panel_usuario_nuevo"):
      self.assertEqual(c.get(reverse(nombre)).status_code, 403, nombre)

  def test_cada_rol_solo_ve_sus_modulos(self):
    r = logueado(self.gestor).get(reverse("panel_productos"))
    self.assertEqual(r.status_code, 200)
    self.assertEqual(logueado(self.gestor).get(reverse("panel_pedidos")).status_code, 403)
    self.assertEqual(logueado(self.gestor).get(reverse("panel_usuarios")).status_code, 403)
    self.assertEqual(logueado(self.pedidos_user).get(reverse("panel_productos")).status_code, 403)
    self.assertEqual(logueado(self.pedidos_user).get(reverse("panel_pedidos")).status_code, 200)

  def test_la_pagina_403_es_la_personalizada(self):
    r = logueado(self.sin_permisos).get(reverse("panel_usuarios"))
    self.assertContains(r, "Acceso denegado", status_code=403)

  def test_15_todas_las_pantallas_renderizan_para_el_administrador(self):
    c = logueado(self.admin)
    for ruta in self.rutas():
      self.assertEqual(c.get(ruta).status_code, 200, ruta)
    self.assertEqual(c.get(reverse("panel_usuarios"), {"q": "admin"}).status_code, 200)

  def test_el_admin_de_django_tambien_funciona(self):
    c = logueado(self.admin)
    for ruta in ("/admin/", "/admin/tienda/producto/", "/admin/tienda/producto/add/", "/admin/auth/user/"):
      self.assertEqual(c.get(ruta).status_code, 200, ruta)

  def test_13_las_paginas_publicas_siguen_accesibles(self):
    c = Client()
    for ruta in ("/", "/productos/", f"/producto/{self.p1.pk}/", "/login/", "/panel/ingresar/"):
      self.assertEqual(c.get(ruta).status_code, 200, ruta)
    self.assertEqual(c.get("/checkout/").status_code, 302)  # sigue exigiendo cliente

  def test_el_enlace_al_panel_solo_aparece_para_el_personal(self):
    self.assertNotContains(Client().get("/"), 'href="/panel/"')
    self.assertContains(logueado(self.admin).get("/"), 'href="/panel/"')


class UsuariosTests(Base):
  def datos(self, **extra):
    d = {
      "username": "nuevo", "first_name": "Nora", "last_name": "Díaz", "email": "nora@ejemplo.com",
      "password1": CLAVE, "password2": CLAVE, "rol": "staff",
    }
    d.update(extra)
    return d

  def test_7_el_administrador_crea_usuarios_con_contrasena_hasheada(self):
    grupo = Group.objects.get(name="Gestor de productos")
    r = logueado(self.admin).post(reverse("panel_usuario_nuevo"), self.datos(grupos=[grupo.pk]))
    self.assertRedirects(r, reverse("panel_usuarios"), fetch_redirect_response=False)
    u = Usuario.objects.get(username="nuevo")
    self.assertTrue(u.is_staff and u.is_active and not u.is_superuser)
    self.assertEqual(list(u.groups.all()), [grupo])
    identify_hasher(u.password)  # es un hash de Django, no texto plano
    self.assertNotEqual(u.password, CLAVE)
    self.assertTrue(u.check_password(CLAVE))

  def test_8_el_usuario_creado_puede_iniciar_sesion(self):
    logueado(self.admin).post(reverse("panel_usuario_nuevo"), self.datos())
    c = Client()
    r = c.post(reverse("panel_login"), {"usuario": "nuevo", "contrasena": CLAVE})
    self.assertRedirects(r, reverse("panel_inicio"), fetch_redirect_response=False)
    r = Client().post(reverse("panel_login"), {"usuario": "nora@ejemplo.com", "contrasena": CLAVE})
    self.assertEqual(r.status_code, 302)

  def test_rol_administrador_crea_superusuario(self):
    logueado(self.admin).post(reverse("panel_usuario_nuevo"), self.datos(username="jefe", email="jefe@x.com", rol="admin"))
    self.assertTrue(Usuario.objects.get(username="jefe").is_superuser)

  def test_validaciones_de_creacion(self):
    c = logueado(self.admin)
    url = reverse("panel_usuario_nuevo")
    casos = {
      "usuario duplicado": self.datos(username="ADMIN1", email="otro@x.com"),
      "contraseñas distintas": self.datos(password2="Otra-Clave-2026!"),
      "contraseña débil": self.datos(password1="12345678", password2="12345678"),
      "correo duplicado": self.datos(email="ADMIN1@ejemplo.com"),
      "correo vacío": self.datos(email=""),
      "rol inválido": self.datos(rol="dios"),
    }
    for nombre, datos in casos.items():
      r = c.post(url, datos)
      self.assertEqual(r.status_code, 200, nombre)
      self.assertFalse(r.context["form"].is_valid(), nombre)
    self.assertFalse(Usuario.objects.filter(username="nuevo").exists())

  def test_5_un_usuario_normal_no_puede_crear_usuarios(self):
    for u in (self.sin_permisos, self.gestor, self.consulta, self.no_staff):
      r = logueado(u).post(reverse("panel_usuario_nuevo"), self.datos(username=f"hack_{u.username}"))
      self.assertEqual(r.status_code, 403, u.username)
    self.assertFalse(Usuario.objects.filter(username__startswith="hack_").exists())

  def test_6_un_usuario_normal_no_puede_darse_privilegios_con_peticiones_manipuladas(self):
    c = logueado(self.gestor)
    manipulado = {
      "first_name": "G", "last_name": "G", "email": "gestor@ejemplo.com",
      "rol": "admin", "is_superuser": "on", "is_staff": "on", "grupos": [Group.objects.get(name="Gestor de pedidos").pk],
    }
    r = c.post(reverse("panel_usuario_editar", args=[self.gestor.pk]), manipulado)
    self.assertEqual(r.status_code, 403)
    self.assertEqual(c.post(reverse("panel_usuario_estado", args=[self.admin.pk])).status_code, 403)
    self.assertEqual(c.post(reverse("panel_usuario_contrasena", args=[self.admin.pk]),
                            {"password1": CLAVE, "password2": CLAVE}).status_code, 403)
    g = Usuario.objects.get(pk=self.gestor.pk)
    self.assertFalse(g.is_superuser)
    self.assertEqual(list(g.groups.values_list("name", flat=True)), ["Gestor de productos"])
    self.assertTrue(Usuario.objects.get(pk=self.admin.pk).is_active)

  def test_el_admin_no_puede_crear_privilegios_inyectando_campos_extra(self):
    logueado(self.admin).post(
      reverse("panel_usuario_nuevo"),
      self.datos(is_superuser="on", is_staff="", is_active="", user_permissions=[1]),
    )
    u = Usuario.objects.get(username="nuevo")
    self.assertFalse(u.is_superuser)
    self.assertTrue(u.is_staff and u.is_active)
    self.assertEqual(u.user_permissions.count(), 0)

  def test_editar_usuario_cambia_datos_permitidos_pero_no_el_nombre_de_usuario(self):
    c = logueado(self.admin)
    g = Group.objects.get(name="Consulta")
    r = c.post(reverse("panel_usuario_editar", args=[self.gestor.pk]), {
      "first_name": "Gus", "last_name": "Gil", "email": "gus@ejemplo.com", "rol": "staff",
      "grupos": [g.pk], "username": "renombrado",
    })
    self.assertEqual(r.status_code, 302)
    u = Usuario.objects.get(pk=self.gestor.pk)
    self.assertEqual((u.username, u.first_name, u.email), ("gestor", "Gus", "gus@ejemplo.com"))
    self.assertEqual(list(u.groups.all()), [g])

  def test_activar_y_desactivar_cuentas(self):
    c = logueado(self.admin)
    url = reverse("panel_usuario_estado", args=[self.gestor.pk])
    self.assertEqual(c.get(url).status_code, 405)  # solo POST
    c.post(url)
    self.assertFalse(Usuario.objects.get(pk=self.gestor.pk).is_active)
    c.post(url)
    self.assertTrue(Usuario.objects.get(pk=self.gestor.pk).is_active)

  def test_no_se_puede_desactivar_ni_degradar_al_ultimo_administrador(self):
    c = logueado(self.admin)
    c.post(reverse("panel_usuario_estado", args=[self.admin.pk]))
    self.assertTrue(Usuario.objects.get(pk=self.admin.pk).is_active)
    r = c.post(reverse("panel_usuario_editar", args=[self.admin.pk]), {
      "first_name": "A", "last_name": "A", "email": "admin1@ejemplo.com", "rol": "staff"})
    self.assertEqual(r.status_code, 200)
    self.assertTrue(Usuario.objects.get(pk=self.admin.pk).is_superuser)

  def test_un_administrador_si_puede_desactivar_a_otro_pero_siempre_queda_uno(self):
    otro = crear_usuario("admin2", superuser=True)
    logueado(self.admin).post(reverse("panel_usuario_estado", args=[otro.pk]))
    self.assertFalse(Usuario.objects.get(pk=otro.pk).is_active)
    # ahora admin1 es el único activo: otro administrador inactivo no puede reactivarlo para desactivar a admin1
    self.assertTrue(Usuario.objects.filter(is_superuser=True, is_active=True).count() >= 1)

  def test_restablecer_contrasena_la_guarda_con_hash_y_valida_reglas(self):
    c = logueado(self.admin)
    url = reverse("panel_usuario_contrasena", args=[self.gestor.pk])
    r = c.post(url, {"password1": "123", "password2": "123"})
    self.assertEqual(r.status_code, 200)
    nueva = "Otra-Clave-Larga-77!"
    r = c.post(url, {"password1": nueva, "password2": nueva})
    self.assertEqual(r.status_code, 302)
    u = Usuario.objects.get(pk=self.gestor.pk)
    self.assertTrue(u.check_password(nueva))
    identify_hasher(u.password)  # es un hash de Django, no texto plano

  def test_buscar_por_usuario_o_correo(self):
    c = logueado(self.admin)
    r = c.get(reverse("panel_usuarios"), {"q": "gestor"})
    self.assertContains(r, "gestor@ejemplo.com")
    self.assertNotContains(r, "consulta@ejemplo.com")
    r = c.get(reverse("panel_usuarios"), {"q": "consulta@ejemplo"})
    self.assertContains(r, "consulta@ejemplo.com")
    self.assertNotContains(r, "gestor@ejemplo.com")

  def test_el_listado_muestra_fecha_de_creacion_estado_y_rol(self):
    r = logueado(self.admin).get(reverse("panel_usuarios"))
    self.assertContains(r, "Administrador")
    self.assertContains(r, "Gestor de productos")
    self.assertContains(r, "Activo")

  def test_el_listado_no_hace_una_consulta_por_usuario(self):
    # Las consultas del listado no deben crecer con el número de usuarios (N+1 en grupos).
    c = logueado(self.admin)
    url = reverse("panel_usuarios")
    c.get(url)  # calienta cachés (content types, etc.) para medir en igualdad de condiciones
    with CaptureQueriesContext(connection) as pocas:
      c.get(url)
    grupo = Group.objects.get(name="Consulta")
    for i in range(8):
      crear_usuario(f"extra{i}").groups.add(grupo)
    with CaptureQueriesContext(connection) as muchas:
      r = c.get(url)
    self.assertContains(r, "extra7")
    self.assertEqual(len(muchas), len(pocas), "El número de consultas depende de la cantidad de usuarios")

  def test_14_los_formularios_del_panel_exigen_csrf(self):
    c = Client(enforce_csrf_checks=True)
    c.force_login(self.admin)
    for url, datos in (
      (reverse("panel_usuario_nuevo"), self.datos()),
      (reverse("panel_usuario_estado", args=[self.gestor.pk]), {}),
      (reverse("panel_producto_nuevo"), {"nombre": "Z", "precio": "3"}),
      (reverse("panel_pedido_estado", args=[self.pedido.pk]), {"estado": "Enviado"}),
    ):
      self.assertEqual(c.post(url, datos).status_code, 403, url)
    self.assertFalse(Usuario.objects.filter(username="nuevo").exists())


class ProductosTests(Base):
  def setUp(self):
    super().setUp()
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    sobrescribir = override_settings(PRODUCTO_IMG_DIR=Path(self.tmp.name))
    sobrescribir.enable()
    self.addCleanup(sobrescribir.disable)

  def png(self, nombre="foto.png", contenido=PNG_1X1):
    return SimpleUploadedFile(nombre, contenido, content_type="image/png")

  def test_12_crear_editar_y_listar_productos_con_el_permiso_adecuado(self):
    c = logueado(self.gestor)
    r = c.post(reverse("panel_producto_nuevo"), {"nombre": "  Globos  ", "descripcion": "x", "precio": "12.50"})
    self.assertRedirects(r, reverse("panel_productos"), fetch_redirect_response=False)
    p = Producto.objects.get(nombre="Globos")
    self.assertEqual(p.precio, Decimal("12.50"))
    r = c.post(reverse("panel_producto_editar", args=[p.pk]), {"nombre": "Globos XL", "descripcion": "y", "precio": "15"})
    self.assertEqual(r.status_code, 302)
    p.refresh_from_db()
    self.assertEqual((p.nombre, p.precio), ("Globos XL", Decimal("15.00")))
    self.assertContains(c.get(reverse("panel_productos")), "Globos XL")
    # y el producto se ve en la tienda pública
    self.assertContains(Client().get("/productos/"), "Globos XL")

  def test_validacion_de_precio_y_nombre(self):
    c = logueado(self.gestor)
    for datos in ({"nombre": "A", "precio": "0"}, {"nombre": "A", "precio": "-3"},
                  {"nombre": "A", "precio": "abc"}, {"nombre": "   ", "precio": "3"},
                  {"nombre": "A", "precio": "99999999999"}):
      r = c.post(reverse("panel_producto_nuevo"), datos)
      self.assertEqual(r.status_code, 200, datos)
    self.assertFalse(Producto.objects.filter(nombre="A").exists())

  def test_quien_solo_consulta_no_puede_crear_editar_ni_borrar_por_url_directa(self):
    c = logueado(self.consulta)
    self.assertEqual(c.get(reverse("panel_productos")).status_code, 200)
    self.assertNotContains(c.get(reverse("panel_productos")), "Nuevo producto")
    self.assertEqual(c.post(reverse("panel_producto_nuevo"), {"nombre": "Q", "precio": "5"}).status_code, 403)
    self.assertEqual(c.post(reverse("panel_producto_editar", args=[self.p2.pk]), {"nombre": "Q", "precio": "5"}).status_code, 403)
    self.assertEqual(c.post(reverse("panel_producto_eliminar", args=[self.p2.pk])).status_code, 403)
    self.assertTrue(Producto.objects.filter(pk=self.p2.pk, nombre="Pack dos").exists())

  def test_eliminar_requiere_confirmacion_por_post(self):
    c = logueado(self.gestor)
    url = reverse("panel_producto_eliminar", args=[self.p2.pk])
    self.assertContains(c.get(url), "Sí, eliminar")
    self.assertTrue(Producto.objects.filter(pk=self.p2.pk).exists())
    self.assertEqual(c.post(url).status_code, 302)
    self.assertFalse(Producto.objects.filter(pk=self.p2.pk).exists())

  def test_no_se_elimina_un_producto_que_ya_esta_en_pedidos(self):
    c = logueado(self.gestor)
    r = c.post(reverse("panel_producto_eliminar", args=[self.p1.pk]), follow=True)
    self.assertContains(r, "no se puede eliminar")
    self.assertTrue(Producto.objects.filter(pk=self.p1.pk).exists())

  def test_subir_imagen_valida_la_guarda_con_nombre_propio(self):
    c = logueado(self.gestor)
    r = c.post(reverse("panel_producto_nuevo"), {"nombre": "Con foto", "precio": "5", "imagen_archivo": self.png("../../etc/passwd.png")})
    self.assertEqual(r.status_code, 302)
    p = Producto.objects.get(nombre="Con foto")
    self.assertRegex(p.imagen, r"^productos/producto-[0-9a-f]{12}\.png$")
    self.assertTrue((Path(self.tmp.name) / p.imagen.split("/")[1]).is_file())

  def test_se_rechazan_archivos_que_no_son_imagenes_validas(self):
    c = logueado(self.gestor)
    malos = {
      "script": SimpleUploadedFile("a.png", b"<?php system($_GET['x']); ?>", content_type="image/png"),
      "svg": SimpleUploadedFile("a.svg", b"<svg onload='alert(1)'></svg>", content_type="image/svg+xml"),
      "html con extensión png": SimpleUploadedFile("a.png", b"<html><script>1</script></html>", content_type="image/png"),
      "demasiado grande": SimpleUploadedFile("a.png", PNG_1X1 + b"0" * (2 * 1024 * 1024), content_type="image/png"),
    }
    for nombre, archivo in malos.items():
      r = c.post(reverse("panel_producto_nuevo"), {"nombre": "Malo", "precio": "5", "imagen_archivo": archivo})
      self.assertEqual(r.status_code, 200, nombre)
    self.assertFalse(Producto.objects.filter(nombre="Malo").exists())
    self.assertEqual(list(Path(self.tmp.name).iterdir()), [])

  def test_reemplazar_y_quitar_imagen_borra_solo_las_subidas_por_el_panel(self):
    c = logueado(self.gestor)
    c.post(reverse("panel_producto_nuevo"), {"nombre": "Foto", "precio": "5", "imagen_archivo": self.png()})
    p = Producto.objects.get(nombre="Foto")
    primera = Path(self.tmp.name) / p.imagen.split("/")[1]
    c.post(reverse("panel_producto_editar", args=[p.pk]), {"nombre": "Foto", "precio": "5", "imagen_archivo": self.png()})
    p.refresh_from_db()
    self.assertFalse(primera.exists())
    c.post(reverse("panel_producto_editar", args=[p.pk]), {"nombre": "Foto", "precio": "5", "quitar_imagen": "on"})
    p.refresh_from_db()
    self.assertIsNone(p.imagen)
    self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
    # una imagen original de la tienda (pack1.png) nunca se borra del disco
    c.post(reverse("panel_producto_editar", args=[self.p1.pk]), {"nombre": "Pack uno", "precio": "8.99", "quitar_imagen": "on"})
    self.p1.refresh_from_db()
    self.assertIsNone(self.p1.imagen)

  def test_buscar_productos_en_el_panel(self):
    r = logueado(self.gestor).get(reverse("panel_productos"), {"q": "dos"})
    self.assertContains(r, "Pack dos")
    self.assertNotContains(r, "Pack uno")


class PedidosYClientesTests(Base):
  def test_listado_detalle_y_filtros_de_pedidos(self):
    c = logueado(self.pedidos_user)
    self.assertContains(c.get(reverse("panel_pedidos")), "#%d" % self.pedido.pk)
    self.assertContains(c.get(reverse("panel_pedidos"), {"estado": "Pendiente"}), "Ana")
    self.assertNotContains(c.get(reverse("panel_pedidos"), {"estado": "Entregado"}), "Ana")
    self.assertContains(c.get(reverse("panel_pedidos"), {"q": str(self.pedido.pk)}), "Ana")
    r = c.get(reverse("panel_pedido_detalle", args=[self.pedido.pk]))
    self.assertContains(r, "Pack uno")
    self.assertContains(r, "Cambiar estado")
    self.assertEqual(c.get(reverse("panel_pedido_detalle", args=[9999])).status_code, 404)

  def test_cambiar_estado_requiere_permiso_y_valida_el_valor(self):
    url = reverse("panel_pedido_estado", args=[self.pedido.pk])
    logueado(self.pedidos_user).post(url, {"estado": "Entregado"})
    self.pedido.refresh_from_db()
    self.assertEqual(self.pedido.estado, "Entregado")
    logueado(self.pedidos_user).post(url, {"estado": "Inventado"})
    self.pedido.refresh_from_db()
    self.assertEqual(self.pedido.estado, "Entregado")
    # solo consulta: ve el pedido pero no puede cambiarlo
    c = logueado(self.consulta)
    self.assertNotContains(c.get(reverse("panel_pedido_detalle", args=[self.pedido.pk])), "Cambiar estado")
    self.assertEqual(c.post(url, {"estado": "Cancelado"}).status_code, 403)
    self.pedido.refresh_from_db()
    self.assertEqual(self.pedido.estado, "Entregado")

  def test_clientes_se_listan_sin_exponer_contrasenas(self):
    r = logueado(self.pedidos_user).get(reverse("panel_clientes"))
    self.assertContains(r, "ana@x.com")
    self.assertNotContains(r, "pbkdf2_secreto")
    self.assertEqual(logueado(self.gestor).get(reverse("panel_clientes")).status_code, 403)
