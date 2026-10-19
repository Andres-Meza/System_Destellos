import json
import uuid
from decimal import Decimal
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse

from .carrito import MAX_CANTIDAD
from .models import CarritoCliente, Cliente, DetallePedido, Pedido, PedidoToken, Producto
from .templatetags.tienda_extras import precio


def post_json(client, nombre_url, datos, **extra):
    return client.post(reverse(nombre_url), data=json.dumps(datos), content_type="application/json", **extra)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p1 = Producto.objects.create(nombre="Pack uno", descripcion="Descripcion larga del pack uno", precio=Decimal("8.99"), imagen="pack1.png")
        cls.p2 = Producto.objects.create(nombre="Pack dos", descripcion="Otra descripcion", precio=Decimal("39.99"), imagen="")
        cls.p3 = Producto.objects.create(nombre="Globos 45000", descripcion=None, precio=Decimal("45000.00"))
        cls.ana = Cliente.objects.create(nombre="Ana", correo="ana@x.com", contrasena="x", direccion="Calle 1")
        cls.beto = Cliente.objects.create(nombre="Beto", correo="beto@x.com", contrasena="x")

    def entrar(self, cliente, client=None):
        c = client or self.client
        s = c.session
        s["id_cliente"] = cliente.pk
        s.save()
        return c

    @staticmethod
    def items(*pares):
        return [{"id": i, "qty": q} for i, q in pares]


class CatalogoTests(Base):
    def test_tarjetas_muestran_nombre_y_precio_sin_descripcion(self):
        r = self.client.get(reverse("productos"))
        self.assertContains(r, "Pack uno")
        self.assertContains(r, "$8,99")
        self.assertContains(r, "$45.000")
        self.assertNotContains(r, "Descripcion larga del pack uno")

    def test_producto_sin_imagen_no_rompe_y_tiene_marcador(self):
        r = self.client.get(reverse("productos"))
        self.assertContains(r, "p-card__placeholder")
        self.assertEqual(r.status_code, 200)

    def test_cada_tarjeta_enlaza_al_detalle(self):
        r = self.client.get(reverse("productos"))
        self.assertContains(r, reverse("producto_detalle", args=[self.p1.pk]))

    def test_detalle_muestra_informacion_completa_disponible(self):
        r = self.client.get(reverse("producto_detalle", args=[self.p1.pk]))
        self.assertContains(r, "Descripcion larga del pack uno")
        self.assertContains(r, "$8,99")
        self.assertContains(r, "Agregar al carrito")
        self.assertContains(r, 'data-max="%d"' % MAX_CANTIDAD)

    def test_detalle_inexistente_404(self):
        self.assertEqual(self.client.get(reverse("producto_detalle", args=[9999])).status_code, 404)

    def test_busqueda(self):
        r = self.client.get(reverse("productos"), {"q": "dos"})
        self.assertContains(r, "Pack dos")
        self.assertNotContains(r, "Pack uno")
        r = self.client.get(reverse("productos"), {"q": "zzzz"})
        self.assertContains(r, "No encontramos productos")

    def test_paginacion(self):
        for i in range(15):
            Producto.objects.create(nombre=f"Extra {i}", precio=Decimal("1.00"))
        r = self.client.get(reverse("productos"))
        self.assertTrue(r.context["pagina"].has_next())
        self.assertEqual(len(r.context["pagina"]), 12)

    def test_formato_precio(self):
        self.assertEqual(precio(Decimal("8.99")), "$8,99")
        self.assertEqual(precio(Decimal("79990.00")), "$79.990")
        self.assertEqual(precio(Decimal("1234567.50")), "$1.234.567,50")
        self.assertEqual(precio(Decimal("0")), "$0")


class ValidarTests(Base):
    def test_precios_vienen_del_servidor_y_se_ignora_lo_que_envia_js(self):
        r = post_json(self.client, "api_carrito_validar",
                      {"items": [{"id": self.p1.pk, "qty": 3, "precio": "0.01", "subtotal": "0.03"}]})
        d = r.json()
        self.assertEqual(d["lineas"][0]["precio"], "8.99")
        self.assertEqual(d["lineas"][0]["subtotal"], "26.97")
        self.assertEqual(d["total"], "26.97")

    def test_total_suma_de_subtotales(self):
        d = post_json(self.client, "api_carrito_validar",
                      {"items": self.items((self.p1.pk, 2), (self.p2.pk, 1))}).json()
        self.assertEqual(Decimal(d["total"]), Decimal("8.99") * 2 + Decimal("39.99"))
        self.assertEqual(d["unidades"], 3)

    def test_cantidades_invalidas_rechazadas(self):
        for malo in (0, -1, 1.5, "2", True, None):
            r = post_json(self.client, "api_carrito_validar", {"items": [{"id": self.p1.pk, "qty": malo}]})
            self.assertEqual(r.status_code, 400, malo)
            self.assertEqual(r.json()["codigo"], "cantidad_invalida", malo)

    def test_cantidad_sobre_maximo_se_recorta_al_mostrar(self):
        d = post_json(self.client, "api_carrito_validar", {"items": self.items((self.p1.pk, 500))}).json()
        self.assertEqual(d["lineas"][0]["qty"], MAX_CANTIDAD)

    def test_producto_inexistente_se_reporta(self):
        d = post_json(self.client, "api_carrito_validar", {"items": self.items((9999, 1), (self.p1.pk, 1))}).json()
        self.assertEqual(d["no_disponibles"], [9999])
        self.assertEqual(len(d["lineas"]), 1)

    def test_lineas_repetidas_se_suman_no_se_duplican(self):
        d = post_json(self.client, "api_carrito_validar", {"items": self.items((self.p1.pk, 1), (self.p1.pk, 2))}).json()
        self.assertEqual(len(d["lineas"]), 1)
        self.assertEqual(d["lineas"][0]["qty"], 3)

    def test_json_invalido_y_metodo_get(self):
        r = self.client.post(reverse("api_carrito_validar"), data="no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(reverse("api_carrito_validar")).status_code, 405)

    def test_formato_de_items_invalido(self):
        for malo in ("x", {"a": 1}, [1, 2], [{"id": "3", "qty": 1}]):
            r = post_json(self.client, "api_carrito_validar", {"items": malo})
            self.assertEqual(r.status_code, 400, malo)

    def test_csrf_se_exige(self):
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("api_carrito_validar"), data=json.dumps({"items": []}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
        r = c.post(reverse("api_checkout"), data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 403)
        r = c.post(reverse("api_carrito_sync"), data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_csrf_correcto_funciona(self):
        c = Client(enforce_csrf_checks=True)
        token = c.get(reverse("productos")).context["tienda_config"]["csrf"]
        r = c.post(reverse("api_carrito_validar"), data=json.dumps({"items": []}),
                   content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)


class SyncTests(Base):
    def sync(self, items, owner=None, dirty=False, base=None, cliente=None):
        c = self.entrar(cliente or self.ana, Client())
        r = post_json(c, "api_carrito_sync", {"items": items, "owner": owner, "dirty": dirty, "base": base})
        return r, r.json()

    def qtys(self, d):
        return {l["id"]: l["qty"] for l in d["lineas"]}

    def test_anonimo_no_sincroniza(self):
        r = post_json(self.client, "api_carrito_sync", {"items": []})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["codigo"], "no_autenticado")

    def test_carrito_anonimo_se_fusiona_con_el_del_servidor_usando_el_mayor(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p1.pk): 2, str(self.p2.pk): 1}, version=3)
        _, d = self.sync(self.items((self.p1.pk, 5), (self.p3.pk, 1)), owner=None, dirty=True)
        self.assertEqual(self.qtys(d), {self.p1.pk: 5, self.p2.pk: 1, self.p3.pk: 1})
        self.assertEqual(d["accion"], "fusion")

    def test_sincronizar_dos_veces_no_duplica_cantidades(self):
        _, d1 = self.sync(self.items((self.p1.pk, 2)), owner=None, dirty=True)
        _, d2 = self.sync(self.items((self.p1.pk, 2)), owner=None, dirty=True)
        self.assertEqual(self.qtys(d1), self.qtys(d2))
        self.assertEqual(self.qtys(d2), {self.p1.pk: 2})

    def test_local_con_cambios_y_base_vigente_gana_y_propaga_borrados(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p1.pk): 2, str(self.p2.pk): 1}, version=4)
        _, d = self.sync(self.items((self.p1.pk, 2)), owner=self.ana.pk, dirty=True, base=4)
        self.assertEqual(self.qtys(d), {self.p1.pk: 2})
        self.assertEqual(d["accion"], "local")
        self.assertEqual(CarritoCliente.objects.get(cliente=self.ana).version, 5)

    def test_conflicto_con_otro_dispositivo_se_fusiona(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p2.pk): 1}, version=7)
        _, d = self.sync(self.items((self.p1.pk, 2)), owner=self.ana.pk, dirty=True, base=4)
        self.assertEqual(self.qtys(d), {self.p1.pk: 2, self.p2.pk: 1})
        self.assertEqual(d["accion"], "fusion")

    def test_sin_cambios_locales_gana_el_servidor(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p2.pk): 3}, version=2)
        _, d = self.sync(self.items((self.p1.pk, 9)), owner=self.ana.pk, dirty=False, base=1)
        self.assertEqual(self.qtys(d), {self.p2.pk: 3})
        self.assertEqual(d["accion"], "servidor")

    def test_carrito_local_de_otra_cuenta_se_descarta(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p2.pk): 1}, version=1)
        _, d = self.sync(self.items((self.p1.pk, 9)), owner=self.beto.pk, dirty=True, base=1)
        self.assertEqual(self.qtys(d), {self.p2.pk: 1})

    def test_productos_inexistentes_se_eliminan(self):
        _, d = self.sync(self.items((9999, 2), (self.p1.pk, 1)), owner=None, dirty=True)
        self.assertEqual(self.qtys(d), {self.p1.pk: 1})

    def test_el_carrito_guardado_no_contiene_precios(self):
        self.sync(self.items((self.p1.pk, 2)), owner=None, dirty=True)
        datos = CarritoCliente.objects.get(cliente=self.ana).datos
        self.assertEqual(datos, {str(self.p1.pk): 2})


class CheckoutTests(Base):
    def setUp(self):
        self.c = self.entrar(self.ana, Client())

    def comprar(self, items, token=None, total_visto=None, client=None):
        datos = {"token": str(token or uuid.uuid4()), "items": items}
        if total_visto is not None:
            datos["total_visto"] = total_visto
        return post_json(client or self.c, "api_checkout", datos)

    def test_requiere_sesion(self):
        r = self.comprar(self.items((self.p1.pk, 1)), client=Client())
        self.assertEqual(r.status_code, 401)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_crea_pedido_con_precios_y_total_calculados_por_el_servidor(self):
        r = self.comprar(self.items((self.p1.pk, 2), (self.p2.pk, 1)))
        d = r.json()
        self.assertEqual(r.status_code, 201)
        self.assertTrue(d["ok"])
        pedido = Pedido.objects.get(pk=d["id_pedido"])
        self.assertEqual(pedido.total, Decimal("57.97"))   # 8.99*2 + 39.99
        self.assertEqual(pedido.cliente_id, self.ana.pk)
        self.assertEqual(pedido.estado, "Pendiente")
        detalles = {x.producto_id: (x.cantidad, x.precio_unitario) for x in pedido.detalles.all()}
        self.assertEqual(detalles, {self.p1.pk: (2, Decimal("8.99")), self.p2.pk: (1, Decimal("39.99"))})

    def test_precio_modificado_en_servidor_se_revalida_antes_de_confirmar(self):
        visto = "17.98"                      # el cliente vio 2 x 8.99
        Producto.objects.filter(pk=self.p1.pk).update(precio=Decimal("10.00"))
        r = self.comprar(self.items((self.p1.pk, 2)), total_visto=visto)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "precio_cambiado")
        self.assertEqual(r.json()["total"], "20.00")
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(PedidoToken.objects.count(), 0)   # no se consume el token

    def test_si_el_precio_no_cambio_con_total_visto_correcto_compra(self):
        r = self.comprar(self.items((self.p1.pk, 2)), total_visto="17.98")
        self.assertEqual(r.status_code, 201)

    def test_precio_actual_se_usa_aunque_el_cliente_no_envie_total_visto(self):
        Producto.objects.filter(pk=self.p1.pk).update(precio=Decimal("10.00"))
        d = self.comprar(self.items((self.p1.pk, 1))).json()
        self.assertEqual(Pedido.objects.get(pk=d["id_pedido"]).total, Decimal("10.00"))

    def test_producto_inexistente_no_crea_pedido(self):
        r = self.comprar(self.items((self.p1.pk, 1), (9999, 1)))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "productos_no_disponibles")
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(DetallePedido.objects.count(), 0)

    def test_cantidad_invalida_o_excesiva_se_rechaza(self):
        for q in (0, -2, 1.5, MAX_CANTIDAD + 1):
            r = self.comprar([{"id": self.p1.pk, "qty": q}])
            self.assertEqual(r.status_code, 400, q)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_carrito_vacio_y_token_invalido(self):
        self.assertEqual(self.comprar([]).status_code, 400)
        r = post_json(self.c, "api_checkout", {"token": "abc", "items": self.items((self.p1.pk, 1))})
        self.assertEqual(r.json()["codigo"], "token_invalido")

    def test_mismo_token_dos_veces_crea_un_solo_pedido(self):
        tk = uuid.uuid4()
        r1 = self.comprar(self.items((self.p1.pk, 2)), token=tk)
        r2 = self.comprar(self.items((self.p1.pk, 2)), token=tk)
        self.assertEqual((r1.status_code, r2.status_code), (201, 200))
        self.assertTrue(r2.json()["duplicado"])
        self.assertEqual(r1.json()["id_pedido"], r2.json()["id_pedido"])
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(DetallePedido.objects.count(), 1)

    def test_mismo_token_con_contenido_distinto_se_rechaza(self):
        tk = uuid.uuid4()
        self.comprar(self.items((self.p1.pk, 2)), token=tk)
        r = self.comprar(self.items((self.p1.pk, 5)), token=tk)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "token_reutilizado")
        self.assertEqual(Pedido.objects.count(), 1)

    def test_token_de_otro_cliente_no_devuelve_su_pedido(self):
        tk = uuid.uuid4()
        self.comprar(self.items((self.p1.pk, 1)), token=tk)
        otro = self.entrar(self.beto, Client())
        r = self.comprar(self.items((self.p1.pk, 1)), token=tk, client=otro)
        self.assertEqual(r.status_code, 409)
        self.assertNotIn("id_pedido", r.json())

    def test_error_del_servidor_no_se_presenta_como_exito_y_revierte_todo(self):
        with mock.patch("tienda.carrito.DetallePedido.objects.bulk_create", side_effect=RuntimeError("boom")):
            with self.assertLogs("tienda.api", level="ERROR"):
                r = self.comprar(self.items((self.p1.pk, 1)))
        self.assertEqual(r.status_code, 500)
        self.assertFalse(r.json()["ok"])
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(PedidoToken.objects.count(), 0)

    def test_lo_no_comprado_se_conserva_en_el_carrito_guardado(self):
        CarritoCliente.objects.create(
            cliente=self.ana, datos={str(self.p1.pk): 5, str(self.p2.pk): 1}, version=1)
        self.comprar(self.items((self.p1.pk, 2)))
        datos = CarritoCliente.objects.get(cliente=self.ana).datos
        self.assertEqual(datos, {str(self.p1.pk): 3, str(self.p2.pk): 1})

    def test_el_carrito_no_se_borra_si_el_pedido_falla(self):
        CarritoCliente.objects.create(cliente=self.ana, datos={str(self.p1.pk): 2}, version=1)
        self.comprar(self.items((self.p1.pk, 1), (9999, 1)))
        self.assertEqual(CarritoCliente.objects.get(cliente=self.ana).datos, {str(self.p1.pk): 2})


class PedidoYLoginTests(Base):
    def test_pedido_solo_lo_ve_su_dueno(self):
        ped = Pedido.objects.create(cliente=self.ana, fecha="2026-10-15", total=Decimal("8.99"))
        DetallePedido.objects.create(pedido=ped, producto=self.p1, cantidad=1, precio_unitario=Decimal("8.99"))
        self.assertEqual(self.client.get(reverse("pedido_confirmado", args=[ped.pk])).status_code, 302)
        self.entrar(self.beto)
        self.assertEqual(self.client.get(reverse("pedido_confirmado", args=[ped.pk])).status_code, 404)
        self.entrar(self.ana)
        r = self.client.get(reverse("pedido_confirmado", args=[ped.pk]))
        self.assertContains(r, "Pack uno")
        self.assertContains(r, "no se ha realizado ningún cobro")

    def test_checkout_exige_login_y_vuelve_despues(self):
        r = self.client.get(reverse("checkout"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('checkout')}", fetch_redirect_response=False)

    def test_login_respeta_next_interno_e_ignora_externo(self):
        Cliente.objects.filter(pk=self.ana.pk).update(contrasena="clave123")
        r = self.client.post(reverse("login") + "?next=/checkout/", {"correo": "ana@x.com", "contrasena": "clave123"})
        self.assertRedirects(r, "/checkout/", fetch_redirect_response=False)
        self.client.post(reverse("logout"))
        r = self.client.post(reverse("login") + "?next=https://malo.example/", {"correo": "ana@x.com", "contrasena": "clave123"})
        self.assertRedirects(r, reverse("productos"), fetch_redirect_response=False)

    def test_login_sigue_funcionando_sin_next_y_rechaza_clave_mala(self):
        Cliente.objects.filter(pk=self.ana.pk).update(contrasena="clave123")
        r = self.client.post(reverse("login"), {"correo": "ana@x.com", "contrasena": "mala"})
        self.assertContains(r, "incorrectos")
        r = self.client.post(reverse("login"), {"correo": "ana@x.com", "contrasena": "clave123"})
        self.assertRedirects(r, reverse("productos"), fetch_redirect_response=False)

    def test_paginas_publicas_renderizan(self):
        for nombre in ("inicio", "productos", "login"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
