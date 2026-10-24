"""
Pruebas de extremo a extremo con un navegador real (Chromium vía Playwright).

Requisitos:  pip install playwright && playwright install chromium
Uso (con el servidor de desarrollo corriendo en modo SQLite de pruebas):
    python tests_e2e/e2e_playwright.py http://127.0.0.1:8765 db_prueba.sqlite3
"""
import json
import sqlite3
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
DB = sys.argv[2] if len(sys.argv) > 2 else "db_prueba.sqlite3"
SHOTS = "/tmp/shots"
RESULTS = []


def check(nombre, cond, detalle=""):
    RESULTS.append((nombre, bool(cond), detalle))
    print(("  PASS " if cond else "  FAIL ") + nombre + (f"  [{detalle}]" if (detalle and not cond) else ""))


def q(sql, *args):
    con = sqlite3.connect(DB)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def cart_state(page):
    return page.evaluate("JSON.parse(localStorage.getItem('destellos.cart.v1') || 'null')")


def badge_text(page):
    b = page.locator("#cart-badge")
    return b.inner_text() if b.is_visible() else ""


def new_context(browser, **kw):
    ctx = browser.new_context(**kw)
    # El sandbox no tiene internet: las fuentes y GSAP del CDN fallan rápido.
    ctx.route("https://**", lambda r: r.abort())
    return ctx


def watch_errors(page, bucket):
    page.on("pageerror", lambda e: bucket.append("pageerror: " + str(e)))
    page.on("console", lambda m: bucket.append("console.error: " + m.text)
            if m.type == "error" and "Failed to load resource" not in m.text and "ERR_FAILED" not in m.text else None)


def add_from_detail(page, pid, qty=1):
    page.goto(f"{BASE}/producto/{pid}/")
    page.fill("#qty", str(qty))
    page.click("#add-btn")


def login(page, correo="juan@gmail.com", clave="clave_demo_1", next_url=None):
    page.goto(f"{BASE}/login/" + (f"?next={next_url}" if next_url else ""))
    page.fill("#email", correo)
    page.fill("#password", clave)
    page.click("button[type=submit].btn--primary")


def run():
    import os
    os.makedirs(SHOTS, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        errors = []

        # ------------------------------------------------------------------ 1-2
        print("\n[1-2] Catálogo y detalle")
        ctx = new_context(browser, viewport={"width": 1280, "height": 900})
        page = ctx.new_page(); watch_errors(page, errors)
        page.goto(f"{BASE}/productos/")
        cards = page.locator(".p-card")
        check("catálogo muestra 6 tarjetas", cards.count() == 6, cards.count())
        txt = page.locator(".p-card").first.inner_text()
        check("tarjeta muestra nombre y precio", "Pack de decoracion #1" in txt and "$8,99" in txt, txt)
        check("tarjeta NO muestra descripción", "Incluye" not in page.inner_text(".p-grid"))
        check("precio COP con separador de miles", "$45.000" in page.inner_text(".p-grid"))
        check("producto sin imagen muestra marcador", page.locator(".p-card__media.is-empty").count() >= 1)
        page.wait_for_timeout(600)
        check("imagen inexistente cae al marcador", page.locator(".p-card", has_text="Imagen inexistente").locator(".p-card__media.is-empty").count() == 1)
        page.screenshot(path=f"{SHOTS}/01_catalogo.png", full_page=True)
        page.locator(".p-card", has_text="Pack de decoracion #2").click()
        check("clic en tarjeta abre el detalle", "/producto/2/" in page.url, page.url)
        check("detalle muestra descripción completa", "montaje y organización" in page.inner_text(".detail__desc"))
        check("detalle muestra precio", "$39,99" in page.inner_text(".detail__price"))
        page.screenshot(path=f"{SHOTS}/02_detalle.png", full_page=True)

        # ------------------------------------------------------------------ 3
        print("\n[3] Selector de cantidades")
        page.goto(f"{BASE}/producto/1/")
        qty = page.locator("#qty"); err = page.locator("#qty-error")
        minus = page.locator('[data-step="-1"]'); plus = page.locator('[data-step="1"]')
        check("inicia en 1 con 'disminuir' deshabilitado", qty.input_value() == "1" and minus.is_disabled())
        qty.fill("-3")
        check("rechaza negativos (queda 3 solo dígitos) y avisa", qty.input_value() == "3" and err.is_visible())
        qty.fill("2.5")
        check("rechaza decimales", qty.input_value() == "25" and err.is_visible(), qty.input_value())
        qty.fill("0")
        check("0 se corrige a 1 con aviso", qty.input_value() == "1" and "mínima" in err.inner_text())
        qty.fill("abc")
        check("texto no numérico se descarta", qty.input_value() == "" and err.is_visible())
        qty.blur()
        check("vacío al salir vuelve a 1", qty.input_value() == "1")
        qty.fill("150")
        check("sobre el máximo se limita a 99", qty.input_value() == "99" and plus.is_disabled() and "máxima" in err.inner_text())
        qty.fill("5"); plus.click(); plus.click(); minus.click()
        check("botones +/− cambian la cantidad", qty.input_value() == "6", qty.input_value())

        # ------------------------------------------------------------------ 4-5
        print("\n[4-5] Agregar y volver a agregar el mismo producto")
        page.goto(f"{BASE}/producto/1/")
        check("badge oculto con carrito vacío", badge_text(page) == "")
        page.fill("#qty", "2"); page.click("#add-btn")
        check("badge muestra 2 sin recargar", badge_text(page) == "2", badge_text(page))
        check("aparece confirmación discreta", page.locator(".toast").first.is_visible())
        check("nota 'ya tienes 2' en el detalle", "2 unidades" in page.inner_text("#in-cart-note"))
        page.wait_for_timeout(500)
        page.fill("#qty", "3"); page.click("#add-btn")
        st = cart_state(page)
        check("mismo producto SUMA cantidad (5) sin duplicar línea", badge_text(page) == "5" and len(st["items"]) == 1 and st["items"]["1"]["q"] == 5, st)
        page.wait_for_timeout(500)
        add_from_detail(page, 2, 1)
        check("segundo producto: 2 líneas, 6 unidades", badge_text(page) == "6" and len(cart_state(page)["items"]) == 2)
        page.locator("#add-btn").click(); page.wait_for_timeout(500)
        # doble clic accidental rápido
        before = cart_state(page)["items"]["2"]["q"]
        page.evaluate("document.querySelector('#add-btn').click(); document.querySelector('#add-btn').click()")
        page.wait_for_timeout(300)
        check("doble clic rápido no agrega dos veces", cart_state(page)["items"]["2"]["q"] == before + 1, cart_state(page)["items"]["2"])

        # ------------------------------------------------------------------ 6-8
        print("\n[6-8] Panel del carrito: cantidades, totales, eliminar, vaciar")
        page.goto(f"{BASE}/productos/")
        page.click("#cart-open")
        drawer = page.locator("#cart-drawer")
        check("el panel se abre", drawer.is_visible())
        page.wait_for_timeout(500)
        lines = page.locator(".cart-line")
        check("2 líneas en el panel", lines.count() == 2, lines.count())
        # p1 = 5 x 8.99 = 44.95 ; p2 = 2 x 39.99 = 79.98 ; total 124.93
        check("subtotal línea 1 = 5 × $8,99 = $44,95", "$44,95" in lines.nth(0).inner_text(), lines.nth(0).inner_text())
        check("total = $124,93", page.inner_text("#cart-total") == "$124,93", page.inner_text("#cart-total"))
        check("precios verificados con el servidor", "verificados" in page.inner_text("#cart-total-note"), page.inner_text("#cart-total-note"))
        page.screenshot(path=f"{SHOTS}/03_panel.png")
        page.locator('[data-line="1"] [data-act="inc"]').click()
        check("＋ actualiza subtotal y total ($53,94 / $133,92)", "$53,94" in page.inner_text('[data-line="1"]') and page.inner_text("#cart-total") == "$133,92", page.inner_text("#cart-total"))
        check("el foco se conserva tras actualizar", page.evaluate("document.activeElement.dataset.act") == "inc")
        page.locator('[data-line="1"] [data-act="dec"]').click()
        page.locator('[data-line="1"] [data-act="dec"]').click()
        check("− disminuye ($35,96 y total $115,94)", "$35,96" in page.inner_text('[data-line="1"]') and page.inner_text("#cart-total") == "$115,94", page.inner_text("#cart-total"))
        inp = page.locator('[data-line="1"] input'); inp.fill("abc"); inp.blur()
        check("cantidad inválida en el panel se revierte con aviso", cart_state(page)["items"]["1"]["q"] == 4 and page.locator(".cart-line__warn").count() == 1)
        page.locator('[data-line="2"] [data-act="remove"]').click()
        check("eliminar quita la línea", page.locator(".cart-line").count() == 1 and "2" not in cart_state(page)["items"])
        page.reload()
        check("el producto eliminado NO reaparece al recargar", "2" not in cart_state(page)["items"])
        add_from_detail(page, 2, 1)
        page.click("#cart-open"); page.wait_for_timeout(400)
        page.click("#cart-clear")
        check("vaciar pide confirmación", page.locator("#cart-clear-confirm").is_visible())
        page.click("#cart-clear-no")
        check("cancelar conserva el carrito", len(cart_state(page)["items"]) == 2)
        page.click("#cart-clear"); page.click("#cart-clear-yes")
        check("confirmar vacía el carrito", cart_state(page)["items"] == {} and "vacío" in page.inner_text("#cart-body"))
        check("estado vacío elegante y badge oculto", page.locator(".cart-empty").is_visible() and badge_text(page) == "")
        page.reload()
        check("vaciado persiste tras recargar", cart_state(page)["items"] == {})

        # ------------------------------------------------------------------ 9-10
        print("\n[9-10] Persistencia: recargar y navegar")
        add_from_detail(page, 1, 2); page.wait_for_timeout(300)
        add_from_detail(page, 3, 1); page.wait_for_timeout(300)
        page.reload()
        check("recargar conserva productos y cantidades", badge_text(page) == "3" and cart_state(page)["items"]["1"]["q"] == 2)
        for url in ("/", "/productos/", "/login/", "/producto/2/"):
            page.goto(BASE + url)
            assert badge_text(page) == "3", (url, badge_text(page))
        check("navegar entre 4 páginas conserva el carrito (badge 3)", True)
        page2 = ctx.new_page(); page2.goto(f"{BASE}/productos/")
        check("otra pestaña del mismo navegador ve el mismo carrito", badge_text(page2) == "3")
        page.goto(f"{BASE}/producto/2/"); page.click("#add-btn"); page.wait_for_timeout(300)
        page2.wait_for_timeout(300)
        check("la otra pestaña actualiza el badge en vivo (evento storage)", badge_text(page2) == "4", badge_text(page2))
        page2.close()

        # ------------------------------------------------------------------ 11
        print("\n[11] Sin conexión (anónimo)")
        page.goto(f"{BASE}/productos/")
        ctx.set_offline(True)
        page.wait_for_timeout(300)
        check("aparece la barra de 'sin conexión'", page.locator(".offline-bar").is_visible())
        page.click("#cart-open")
        check("sin conexión el carrito sigue visible", page.locator(".cart-line").count() == 3, page.locator(".cart-line").count())
        page.locator('[data-line="1"] [data-act="inc"]').click()
        check("sin conexión se puede modificar", cart_state(page)["items"]["1"]["q"] == 3)
        check("aviso de sin conexión dentro del panel", "Sin conexión" in page.inner_text("#cart-notice"))
        page.click("#cart-checkout")
        check("finalizar compra sin conexión NO navega y avisa", "/checkout" not in page.url and page.locator(".toast--error").count() >= 1, page.url)
        page.keyboard.press("Escape")
        ctx.set_offline(False)
        page.wait_for_timeout(300)
        check("al volver la conexión desaparece la barra", page.locator(".offline-bar").count() == 0)
        page.reload()
        check("tras reconectar y recargar el carrito sigue (badge 5)", badge_text(page) == "5", badge_text(page))

        # ------------------------------------------------------------------ 12-13, login + sync + checkout
        print("\n[12-16] Sesión, sincronización y compra")
        page.goto(f"{BASE}/checkout/")
        check("checkout sin sesión redirige a login con next", "/login/" in page.url and "next=/checkout/" in page.url, page.url)
        page.fill("#email", "juan@gmail.com"); page.fill("#password", "clave_demo_1")
        page.click("button[type=submit].btn--primary")
        page.wait_for_url("**/checkout/")
        check("tras el login vuelve al checkout (next)", page.url.endswith("/checkout/"))
        page.wait_for_selector(".order-lines")
        check("checkout muestra datos del cliente", "Juan Pérez" in page.inner_text(".data-list") and "Bogotá" in page.inner_text(".data-list"))
        check("checkout lista 3 líneas con total del servidor", page.locator(".order-lines li").count() == 3, page.locator(".order-lines li").count())
        # 3x8.99 + 1x79.99 + 1x39.99 = 26.97+79.99+39.99 = 146.95
        check("total del checkout = $146,95", page.inner_text("#co-total") == "$146,95", page.inner_text("#co-total"))
        page.wait_for_timeout(1200)
        cid = q("select id_cliente from clientes where correo='juan@gmail.com'")[0][0]
        row = q("select datos, version from tienda_carritocliente where cliente_id=?", cid)
        srv = json.loads(row[0][0]) if row else {}
        check("el carrito anónimo se fusionó/guardó en la BD al iniciar sesión", srv == {"1": 3, "3": 1, "2": 1}, srv)
        check("el estado local queda con owner y sin cambios pendientes", cart_state(page)["owner"] == cid and cart_state(page)["dirty"] is False, cart_state(page))
        n0 = q("select count(*) from pedidos")[0][0]
        # precio cambia en el servidor mientras el usuario revisa -> 13
        q_exec = sqlite3.connect(DB); q_exec.execute("update productos set precio=10.00 where id_producto=1"); q_exec.commit(); q_exec.close()
        page.click("#co-confirm"); page.wait_for_timeout(800)
        check("precio cambiado: NO crea pedido", q("select count(*) from pedidos")[0][0] == n0)
        check("precio cambiado: avisa y muestra nuevo total", "precios cambiaron" in page.inner_text("#co-status") and page.inner_text("#co-status").count("confirma de nuevo") == 1 and page.inner_text("#co-total") == "$149,98", page.inner_text("#co-status") + " | " + page.inner_text("#co-total"))
        check("tras el aviso el carrito no se perdió", badge_text(page) == "5")
        # error de red en la compra -> 15
        page.route("**/api/checkout/", lambda r: r.abort())
        page.click("#co-confirm"); page.wait_for_timeout(800)
        check("sin respuesta del servidor: NO se afirma éxito", "pedido registrado" not in page.inner_text("#co-status").lower() and "/pedido/" not in page.url and "no recibimos" in page.inner_text("#co-status").lower(), page.inner_text("#co-status"))
        check("falla de red: pedido no creado y carrito intacto", q("select count(*) from pedidos")[0][0] == n0 and badge_text(page) == "5")
        page.unroute("**/api/checkout/")
        page.route("**/api/checkout/", lambda r: r.fulfill(status=500, content_type="application/json", body='{"ok":false,"codigo":"error_interno","mensaje":"No pudimos registrar tu pedido. No se realizó ningún cargo."}'))
        page.click("#co-confirm"); page.wait_for_timeout(600)
        check("error 500: muestra el error, no éxito", "No pudimos registrar" in page.inner_text("#co-status") and "/pedido/" not in page.url)
        page.unroute("**/api/checkout/")
        # doble clic -> 16 : un solo pedido
        page.evaluate("document.querySelector('#co-confirm').click(); document.querySelector('#co-confirm').click();")
        page.wait_for_url("**/pedido/**", timeout=8000)
        n1 = q("select count(*) from pedidos")[0][0]
        check("doble clic en confirmar crea UN solo pedido", n1 == n0 + 1, (n0, n1))
        pid = int(page.url.rstrip("/").split("/")[-1])
        tot = q("select total from pedidos where id_pedido=?", pid)[0][0]
        check("pedido guardado con el precio vigente del servidor ($149,98)", abs(float(tot) - 149.98) < 0.001, tot)
        dets = q("select id_producto,cantidad,precio_unitario from detalle_pedidos where id_pedido=? order by id_producto", pid)
        check("detalles guardados con precios de la BD", [(d[0], d[1], round(float(d[2]), 2)) for d in dets] == [(1, 3, 10.0), (2, 1, 39.99), (3, 1, 79.99)], dets)
        check("página de confirmación: pago pendiente, sin cobro", "ningún cobro" in page.inner_text("main") and "Pendiente" in page.inner_text("main"))
        page.screenshot(path=f"{SHOTS}/06_pedido.png", full_page=True)
        check("tras comprar el carrito local queda vacío", cart_state(page)["items"] == {} and badge_text(page) == "")
        page.wait_for_timeout(1200)
        srv = q("select datos from tienda_carritocliente where cliente_id=?", cid)[0][0]
        check("el carrito guardado en la BD también quedó vacío", json.loads(srv) == {}, srv)

        # compra parcial conserva lo no comprado: agregar 2, el servidor no tiene uno
        print("\n[12] Reanudar sincronización tras desconexión (con sesión)")
        page.goto(f"{BASE}/productos/")
        add_from_detail(page, 1, 1); page.wait_for_timeout(1500)
        v_before = q("select version from tienda_carritocliente where cliente_id=?", cid)[0][0]
        page.goto(f"{BASE}/productos/"); page.wait_for_timeout(300)
        ctx.set_offline(True); page.wait_for_timeout(200)
        page.click("#cart-open")
        page.locator('[data-line="1"] [data-act="inc"]').click()
        page.locator('[data-line="1"] [data-act="inc"]').click()
        page.wait_for_timeout(1200)
        srv = json.loads(q("select datos from tienda_carritocliente where cliente_id=?", cid)[0][0])
        check("offline: el cambio queda local y pendiente (dirty)", cart_state(page)["items"]["1"]["q"] == 3 and cart_state(page)["dirty"] is True and srv == {"1": 1}, (cart_state(page), srv))
        ctx.set_offline(False)
        page.wait_for_timeout(2500)
        srv = json.loads(q("select datos from tienda_carritocliente where cliente_id=?", cid)[0][0])
        check("al reconectar se sincroniza solo con el servidor (cantidad 3, sin duplicar)", srv == {"1": 3} and cart_state(page)["dirty"] is False, (srv, cart_state(page)))
        page.reload(); page.wait_for_timeout(500)
        srv = json.loads(q("select datos from tienda_carritocliente where cliente_id=?", cid)[0][0])
        check("recargar tras sincronizar no duplica", srv == {"1": 3} and cart_state(page)["items"]["1"]["q"] == 3)

        print("\n[cierre de sesión] el carrito de la cuenta no queda visible para otro usuario")
        page.goto(f"{BASE}/productos/")
        page.click(".primary-nav__account .link-btn")
        page.wait_for_url(f"{BASE}/")
        check("cerrar sesión limpia el carrito local de esa cuenta", cart_state(page)["items"] == {} and badge_text(page) == "")
        login(page, "maria@gmail.com", "clave_demo_2"); page.wait_for_url("**/productos/")
        page.wait_for_timeout(800)
        check("otra cuenta NO hereda el carrito de la anterior", cart_state(page)["items"] == {})
        resp = page.goto(f"{BASE}/pedido/{pid}/")
        check("pedido ajeno no es visible (HTTP 404)", resp.status == 404, resp.status)
        ctx.close()

        # ------------------------------------------------------------------ 17 / 18 móvil y teclado
        print("\n[17] Móvil")
        mob = new_context(browser, viewport={"width": 375, "height": 800}, is_mobile=True, has_touch=True)
        m = mob.new_page(); watch_errors(m, errors)
        for url in ("/", "/productos/", "/producto/1/", "/login/"):
            m.goto(BASE + url)
            ow = m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(f"sin desplazamiento horizontal en {url}", ow <= 0, ow)
        m.goto(f"{BASE}/productos/")
        cols = m.evaluate("getComputedStyle(document.querySelector('.p-grid')).gridTemplateColumns.split(' ').length")
        check("cuadrícula de 2 columnas en móvil", cols == 2, cols)
        check("menú oculto al inicio y botón hamburguesa visible", not m.locator("#primary-nav").is_visible() and m.locator("#mobile-menu").is_visible())
        m.click("#mobile-menu")
        check("menú móvil se abre con links y buscador", m.locator("#primary-nav").is_visible() and m.locator("#buscar").is_visible() and m.get_attribute("#mobile-menu", "aria-expanded") == "true")
        m.screenshot(path=f"{SHOTS}/04_movil_menu.png")
        m.keyboard.press("Escape")
        check("Esc cierra el menú móvil", not m.locator("#primary-nav").is_visible())
        m.fill("#qty", "1") if m.locator("#qty").count() else None
        add_from_detail(m, 3, 2); m.wait_for_timeout(300)
        m.click("#cart-open"); m.wait_for_timeout(400)
        dbox = m.locator("#cart-drawer").bounding_box()
        check("el panel ocupa todo el ancho en móvil", abs(dbox["width"] - 375) < 2, dbox)
        small = m.evaluate("Array.from(document.querySelectorAll('#cart-drawer .stepper__btn')).map(b=>Math.min(b.getBoundingClientRect().width,b.getBoundingClientRect().height))")
        check("botones de cantidad ≥ 40 px (táctiles)", all(s >= 40 for s in small), small)
        m.screenshot(path=f"{SHOTS}/05_movil_carrito.png")
        mob.close()

        print("\n[18] Teclado")
        kb = new_context(browser, viewport={"width": 1280, "height": 800})
        k = kb.new_page(); watch_errors(k, errors)
        k.goto(f"{BASE}/producto/1/")
        k.focus("#cart-open"); k.keyboard.press("Enter"); k.wait_for_timeout(300)
        check("Enter abre el panel y el foco entra en él", k.evaluate("document.getElementById('cart-drawer').contains(document.activeElement)"))
        check("el contenido de fondo es inerte", k.evaluate("document.querySelector('main').hasAttribute('inert')"))
        check("dialog con aria-modal y etiqueta", k.get_attribute("#cart-drawer", "aria-modal") == "true" and k.get_attribute("#cart-drawer", "aria-labelledby") == "cart-title")
        for _ in range(8):
            k.keyboard.press("Tab")
        check("el foco se queda atrapado dentro del panel", k.evaluate("document.getElementById('cart-drawer').contains(document.activeElement)"))
        k.keyboard.press("Escape"); k.wait_for_timeout(300)
        check("Esc cierra y devuelve el foco al botón del carrito", k.evaluate("document.activeElement.id") == "cart-open" and not k.locator("#cart-drawer").is_visible())
        k.focus("#qty"); k.keyboard.type("4"); k.keyboard.press("Tab"); k.keyboard.press("Tab"); k.keyboard.press("Enter")
        check("se puede agregar al carrito solo con teclado", cart_state(k) and "1" in cart_state(k)["items"])
        outline = k.evaluate("(()=>{const b=document.querySelector('#add-btn');b.focus();return getComputedStyle(b).outlineStyle})()")
        check("foco visible en botones", outline != "none", outline)
        kb.close()

        # ------------------------------------------------------------------ almacenamiento bloqueado / manipulado
        print("\n[Almacenamiento bloqueado o corrupto]")
        bl = new_context(browser, viewport={"width": 1280, "height": 800})
        bl.add_init_script("Storage.prototype.setItem = function(){ throw new DOMException('blocked','SecurityError'); };")
        b = bl.new_page(); watch_errors(b, errors)
        b.goto(f"{BASE}/producto/1/"); b.wait_for_timeout(300)
        check("localStorage bloqueado: aviso al usuario", b.locator(".toast--error").count() >= 1)
        b.click("#add-btn"); b.wait_for_timeout(300)
        check("localStorage bloqueado: la página sigue funcionando (memoria)", badge_text(b) == "1")
        b.click("#cart-open"); b.wait_for_timeout(300)
        check("localStorage bloqueado: el panel advierte que no se conservará", "bloquea el almacenamiento" in b.inner_text("#cart-notice"))
        bl.close()

        cr = new_context(browser, viewport={"width": 1280, "height": 800})
        c = cr.new_page(); watch_errors(c, errors)
        c.goto(f"{BASE}/")
        c.evaluate("""localStorage.setItem('destellos.cart.v1', JSON.stringify({v:1,items:{
            '1':{q:2,n:'<img src=x onerror=alert(1)>',p:'8.99',i:'javascript:alert(1)',u:'javascript:alert(2)'},
            'abc':{q:3}, '2':{q:-5,n:'x',p:'1'}, '3':{q:'9999999',n:'ok',p:'abc',i:'//evil.com/x.png',u:'//evil.com'}}}))""")
        c.reload(); c.wait_for_timeout(300)
        st = cart_state(c)
        c.click("#cart-open"); c.wait_for_timeout(300)
        html = c.inner_html("#cart-body")
        check("estado manipulado: se descartan ids/cantidades inválidas", badge_text(c) == "101" or badge_text(c) == "99+", badge_text(c))
        check("estado manipulado: URLs peligrosas anuladas y sin XSS", "javascript:" not in html and "evil.com" not in html and "<img src=x" not in html, html[:200])
        c.evaluate("localStorage.setItem('destellos.cart.v1','{{{{no es json')")
        c.reload(); c.wait_for_timeout(300)
        check("JSON corrupto en localStorage: la página no se rompe", badge_text(c) == "" and c.locator("#cart-open").is_visible())
        cr.close()

        # ------------------------------------------------------------------ GSAP simulado: ejercita las rutas de animación
        print("\n[Animaciones] ruta con GSAP (simulado) sin errores")
        ga = new_context(browser, viewport={"width": 1280, "height": 800})
        ga.add_init_script("""
          window.__g = 0;
          const done = (v)=>{ if (v && v.onComplete) setTimeout(v.onComplete,0); };
          window.gsap = { from(){window.__g++}, fromTo(a,b,c){window.__g++; done(c)}, to(a,v){window.__g++; done(v)},
                          set(){window.__g++}, killTweensOf(){window.__g++} };
        """)
        g = ga.new_page(); watch_errors(g, errors)
        g.goto(f"{BASE}/"); g.goto(f"{BASE}/productos/"); g.goto(f"{BASE}/producto/1/")
        g.click("#add-btn"); g.wait_for_timeout(200)
        g.click("#cart-open"); g.wait_for_timeout(300)
        g.keyboard.press("Escape"); g.wait_for_timeout(300)
        check("las animaciones se invocan (API de GSAP bien usada)", g.evaluate("window.__g") > 5, g.evaluate("window.__g"))
        check("el panel se cierra bien con GSAP", not g.locator("#cart-drawer").is_visible())
        ga.close()
        rm = new_context(browser, viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        rm.add_init_script("window.__g=0; window.gsap={from(){__g++},fromTo(){__g++},to(){__g++},set(){__g++},killTweensOf(){}};")
        r = rm.new_page(); r.goto(f"{BASE}/productos/"); r.click("#cart-open"); r.wait_for_timeout(200)
        check("prefers-reduced-motion: no se lanza ninguna animación GSAP", r.evaluate("window.__g") == 0, r.evaluate("window.__g"))
        rm.close()

        # ------------------------------------------------------------------ inicio / carrusel / páginas sin errores
        print("\n[Inicio] carrusel y consola")
        h = new_context(browser, viewport={"width": 1280, "height": 900})
        hp = h.new_page(); watch_errors(hp, errors)
        hp.goto(f"{BASE}/"); hp.wait_for_timeout(500)
        check("carrusel con 5 diapositivas y 5 puntos", hp.locator(".carousel-slide").count() == 5 and hp.locator("#carousel-dots button").count() == 5)
        hp.click("#carousel-next")
        check("el carrusel avanza", "translateX(-100%)" in hp.get_attribute("#carousel-track", "style"))
        hp.screenshot(path=f"{SHOTS}/00_inicio.png", full_page=True)
        for url in ("/productos/", "/login/", "/producto/1/"):
            hp.goto(BASE + url)
        check("sin errores JS en ninguna página (la del TypeError del carrusel incluida)", not errors, errors)
        h.close()
        browser.close()

    ok = sum(1 for _, c, _ in RESULTS if c)
    print(f"\n==== {ok}/{len(RESULTS)} comprobaciones OK ====")
    for n, c, d in RESULTS:
        if not c:
            print("FALLÓ:", n, d)
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(run())
