# DESTELLOS – Tienda Django + MySQL

## Puesta en marcha
```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # y edita usuario/clave de MySQL

# 1) Importa tu BD una sola vez (phpMyAdmin o consola): base_datos/destellos (1).sql
# 2) Tablas de Django + las 2 tablas nuevas del carrito (NO toca tus tablas originales):
python manage.py migrate
# 3) Carga los 3 packs de ejemplo (solo si la tabla productos está vacía):
python manage.py cargar_productos
# 4) Crea el primer administrador (te pide usuario, correo y contraseña; no hay claves por defecto):
python manage.py createsuperuser
python manage.py runserver
```
Cliente de prueba: juan@gmail.com / clave_demo_1 (al primer ingreso la clave se re-guarda hasheada).

## Pruebas
```bash
# Backend (100 pruebas: tienda, cuentas y panel). Con MySQL necesitas permiso para crear la BD "test_destellos":
python manage.py test
# o sin MySQL, con SQLite temporal:
python manage.py test --settings=config.settings_test
```
Pruebas de navegador (opcional; `pip install playwright && playwright install chromium`):
ver la cabecera de `tests_e2e/e2e_playwright.py`.

## Carrito: cómo funciona
* **Navegador:** `localStorage` (`destellos.cart.v1`) guarda id + cantidad (+ nombre/precio/imagen solo para mostrar).
* **Clientes con sesión:** el carrito se sincroniza con la tabla `tienda_carritocliente` (`/api/carrito/sync/`).
* **Servidor = autoridad:** precios, totales y existencia se leen de `productos` en `/api/carrito/validar/` y `/api/checkout/`.
* **Pedido:** `/api/checkout/` crea `pedidos` + `detalle_pedidos` en una transacción; `PedidoToken` evita duplicados.
* Tope por producto: `CARRITO_MAX_POR_PRODUCTO` en `config/settings.py` (la BD no maneja inventario).

## Panel administrativo (personal)
* **Entrada:** `/panel/ingresar/` (enlace «Acceso del personal» en el pie de la tienda). Usuario **o** correo + contraseña.
  El login de clientes (`/login/`, tabla `clientes`) es independiente y no da acceso al panel.
* **No hay registro público.** Solo un administrador (superusuario) crea cuentas en *Gestión de usuarios* (`/panel/usuarios/`).
* **Roles = grupos y permisos nativos de Django.** Administrador = superusuario (todo + usuarios).
  Usuario administrativo = `is_staff` + grupos que se le asignen: *Gestor de productos*, *Gestor de pedidos*, *Consulta*
  (se crean solos con `migrate`; puedes ajustarlos en `/admin/`). Sin grupos no ve ningún módulo.
* **Módulos:** Resumen, Productos (crear/editar/eliminar/imagen), Pedidos (detalle y estado), Clientes (consulta), Usuarios.
* Las imágenes subidas se guardan en `static/img/productos/` (PNG/JPG/WebP, máx. 2 MB). Con `DEBUG=False` ejecuta `collectstatic` tras subirlas.
* Seguridad: 5 intentos fallidos bloquean 15 min (por IP+usuario); cierre de sesión solo por POST; cookies seguras cuando `DEBUG=False`.

### Python 3.15 y Django 5.0
Django 5.0 no es compatible con Python 3.15 (rompía `/admin/` y 13 pruebas). `config/compat.py` aplica un parche mínimo y se desactiva solo.
Solución definitiva: `pip install "Django>=5.2,<5.3"` (requiere MariaDB ≥ 10.5 o MySQL 8) o usar Python 3.12.
