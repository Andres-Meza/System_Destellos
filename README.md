# Destellos · Tienda virtual de decoración y piñatería

Tienda virtual desarrollada con **Python + Django**, plantillas HTML, CSS, JavaScript y **MySQL**.
Este documento explica, paso a paso y pensando en principiantes, cómo instalar, configurar y ejecutar
el proyecto en Windows (PowerShell).

## Contenido

1. [Presentación del proyecto](#1-presentación-del-proyecto)
2. [Requisitos previos](#2-requisitos-previos)
3. [Instalación paso a paso en Windows](#3-instalación-paso-a-paso-en-windows)
4. [Configuración de la base de datos](#4-configuración-de-la-base-de-datos)
5. [Estructura del proyecto](#5-estructura-del-proyecto)
6. [Guía de uso](#6-guía-de-uso)
7. [Solución de problemas](#7-solución-de-problemas)
8. [Mantenimiento y desarrollo](#8-mantenimiento-y-desarrollo)

---

## 1. Presentación del proyecto

**Destellos** es una tienda virtual de decoración para eventos y piñatería. Permite a los clientes explorar
el catálogo, armar un carrito y registrar pedidos, y ofrece al personal un panel privado para administrar
productos, pedidos, clientes y usuarios.

### Funcionalidades que existen hoy

**Tienda (público)**

* Página de inicio con carrusel de imágenes y sección de características.
* Catálogo de productos con búsqueda y paginación (`/productos/`).
* Detalle de producto con selector de cantidad (`/producto/<id>/`).
* Carrito de compras en un panel lateral: agregar, cambiar cantidades, quitar productos y vaciar el carrito.
* Finalización de compra (`/checkout/`) y página de confirmación del pedido.
* Inicio de sesión de clientes (`/login/`). Los clientes viven en la tabla `clientes`.

**Panel administrativo del personal (`/panel/`)**

* Resumen con indicadores.
* Productos: crear, editar, eliminar y subir imagen.
* Pedidos: listado con filtros, detalle y cambio de estado (Pendiente, En proceso, Enviado, Entregado, Cancelado).
* Clientes: consulta.
* Gestión de usuarios del personal: crear, editar, cambiar contraseña y activar/desactivar.
* Roles basados en los grupos y permisos nativos de Django.

### Tecnologías utilizadas

| Capa | Tecnología |
| --- | --- |
| Backend | Python, Django 5.0 (`Django>=5.0,<5.1`) |
| Base de datos | MySQL / MariaDB (conector `mysqlclient`) |
| Configuración | `python-decouple` (variables en el archivo `.env`) |
| Frontend | Plantillas de Django (HTML), CSS propio, JavaScript sin frameworks |
| Animaciones | GSAP (cargado desde `templates/base.html`) |
| Pruebas | Pruebas de Django (`tienda/tests.py`, `cuentas/tests.py`, `panel/tests.py`) y pruebas de navegador opcionales con Playwright |

---

## 2. Requisitos previos

Instala lo siguiente antes de empezar:

| Herramienta | Para qué sirve | Notas |
| --- | --- | --- |
| **Python 3.12** (recomendado) | Ejecutar Django | Durante la instalación marca **"Add python.exe to PATH"**. Descarga: <https://www.python.org/downloads/> |
| **MySQL Server 8** *(o MariaDB 10.5 o superior)* | Base de datos | También sirve XAMPP, que incluye MariaDB. Si usas MariaDB 10.4 (XAMPP antiguo) mantén Django 5.0, como indica `requirements.txt`. |
| **MySQL Workbench** *(opcional)* | Interfaz gráfica para crear la base de datos e importar el script SQL | <https://dev.mysql.com/downloads/workbench/> |
| **Git** *(opcional)* | Clonar y versionar el proyecto | <https://git-scm.com/downloads> |
| **Visual Studio Code** *(recomendado)* | Editor de código | El proyecto incluye `.vscode/settings.json` |

Las dependencias de Python (`Django`, `mysqlclient`, `python-decouple`) se instalan con `pip` en el paso 4
de la instalación; no necesitas instalarlas a mano.

> **Sobre la versión de Python:** el proyecto se probó con Python 3.12 y Django 5.0. Con Python 3.15,
> Django 5.0 no es compatible por sí solo; el archivo `config/compat.py` aplica un parche mínimo que se activa
> únicamente cuando hace falta. La solución definitiva es usar Python 3.12 o actualizar a `Django>=5.2,<5.3`
> (requiere MySQL 8 o MariaDB 10.5 o superior).

---

## 3. Instalación paso a paso en Windows

Todos los comandos se ejecutan en **PowerShell**.

### Paso 1. Abrir la carpeta raíz del proyecto

La carpeta raíz es la que contiene `manage.py`.

```powershell
cd "C:\ruta\donde\guardaste\tienda_destellos"
dir manage.py
```

Si `dir` muestra el archivo `manage.py`, estás en el lugar correcto.

### Paso 2. Crear el entorno virtual

```powershell
python -m venv venv
```

### Paso 3. Activar el entorno virtual

```powershell
.\venv\Scripts\Activate.ps1
```

Verás `(venv)` al inicio de la línea. Si PowerShell bloquea el script, ejecuta primero esto (solo afecta
a la ventana actual) y vuelve a activar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Paso 4. Instalar las dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

El proyecto **ya incluye** `requirements.txt` con:

```text
Django>=5.0,<5.1
mysqlclient>=2.2
python-decouple>=3.8
```

Para generar o actualizar ese archivo cuando agregues o cambies paquetes (con el entorno activo):

```powershell
pip freeze > requirements.txt
```

> `pip freeze` guarda **todas** las versiones exactas instaladas. Si prefieres conservar el archivo corto,
> edítalo a mano y agrega solo los paquetes que el proyecto usa directamente.

### Paso 5. Configurar las variables de entorno

La configuración sensible se guarda en un archivo `.env` (no se sube a Git). Cópialo desde la plantilla:

```powershell
Copy-Item .env.example .env
notepad .env
```

Variables que reconoce el proyecto (`config/settings.py`):

| Variable | Qué es | Valor por defecto |
| --- | --- | --- |
| `SECRET_KEY` | Clave secreta de Django. **Cámbiala** en cualquier entorno real. | `dev-inseguro-cambiar` |
| `DEBUG` | `True` en desarrollo, `False` en producción. | `True` |
| `ALLOWED_HOSTS` | Dominios permitidos, separados por comas. | `127.0.0.1,localhost` |
| `DB_NAME` | Nombre de la base de datos. | `destellos` |
| `DB_USER` | Usuario de MySQL. | `root` |
| `DB_PASSWORD` | Contraseña de MySQL. | *(vacía)* |
| `DB_HOST` | Servidor de MySQL. | `127.0.0.1` |
| `DB_PORT` | Puerto de MySQL. | `3306` |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | Cookies solo por HTTPS (opcionales). | Automático: activas cuando `DEBUG=False` |
| `SECURE_SSL_REDIRECT` | Redirige todo HTTP a HTTPS (solo producción con HTTPS). | `False` |
| `SECURE_HSTS_SECONDS` | Segundos de HSTS; empieza con un valor bajo (p. ej. `3600`). | `0` (apagado) |
| `USE_X_FORWARDED_PROTO` | `True` si un proxy inverso (nginx) envía `X-Forwarded-Proto`. | `False` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS de confianza, separados por comas (p. ej. `https://tu-dominio.com`). | *(vacía)* |

> Con `DEBUG=False` el proyecto **se niega a arrancar** si `SECRET_KEY` falta o es una clave de ejemplo.

Ejemplo de `.env` (usa tus propios valores, **nunca** publiques el archivo):

```ini
SECRET_KEY=pon-aqui-una-clave-larga-y-aleatoria
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DB_NAME=destellos
DB_USER=root
DB_PASSWORD=tu_contraseña_de_mysql
DB_HOST=127.0.0.1
DB_PORT=3306
```

Para generar una `SECRET_KEY` aleatoria:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Paso 6. Crear la base de datos MySQL y configurar las credenciales

Sigue la [sección 4](#4-configuración-de-la-base-de-datos) y vuelve aquí cuando la base de datos exista
y el `.env` tenga tus credenciales.

### Paso 7. Ejecutar las migraciones de Django

```powershell
python manage.py migrate
```

Este comando crea las tablas propias de Django (usuarios, sesiones, permisos) y las dos tablas del carrito
(`tienda_carritocliente` y `tienda_pedidotoken`). Además crea automáticamente los grupos de roles
*Gestor de productos*, *Gestor de pedidos* y *Consulta*. **No modifica** las tablas originales de la tienda.

### Paso 8. (Opcional) Cargar los productos de ejemplo

Crea los 3 packs de ejemplo, **solo si** la tabla `productos` está vacía:

```powershell
python manage.py cargar_productos
```

### Paso 9. Crear el superusuario administrador

```powershell
python manage.py createsuperuser
```

Te pedirá usuario, correo y contraseña (mínimo 10 caracteres). El proyecto no trae claves por defecto.

### Paso 10. Iniciar el servidor de desarrollo

```powershell
python manage.py runserver
```

### Paso 11. Acceder a la tienda

Abre en el navegador: <http://127.0.0.1:8000/>

### Paso 12. Ingresar al panel administrativo

* **Panel de la tienda (recomendado):** <http://127.0.0.1:8000/panel/ingresar/> con el usuario (o correo) y la
  contraseña del superusuario. También hay un enlace «Acceso del personal» en el pie de la tienda.
* **Administración nativa de Django:** <http://127.0.0.1:8000/admin/>

Para detener el servidor presiona `Ctrl + C`.

---

## 4. Configuración de la base de datos

### 4.1. Cómo funciona la base de datos de este proyecto

Los modelos `Cliente`, `Producto`, `Pedido`, `DetallePedido` y `Pago` están definidos con `managed = False`
(`tienda/models.py`). Eso significa que **Django no crea esas tablas**: se usan las que ya existen en MySQL
(`clientes`, `productos`, `pedidos`, `detalle_pedidos`, `pagos`). Por eso hay que **importar el script SQL
de la base de datos original** antes de ejecutar las migraciones.

> **Importante:** el script SQL no viene incluido en la carpeta del proyecto. La versión anterior de este
> documento lo ubicaba en `base_datos/destellos (1).sql`, pero esa carpeta no existe en el proyecto actual.
> Guarda tu copia del script en `base_datos/` (créala si hace falta) para que cualquier persona pueda
> importarlo. Sin esas tablas, la tienda no puede mostrar productos ni registrar pedidos.

### 4.2. Crear la base de datos

**Opción A: MySQL Workbench**

1. Abre Workbench y conéctate a tu servidor local.
2. Abre una pestaña de consultas y ejecuta:

   ```sql
   CREATE DATABASE destellos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. Importa el script: menú **Server → Data Import → Import from Self-Contained File**, elige tu archivo `.sql`
   y como *Default Target Schema* selecciona `destellos`. Pulsa **Start Import**.

**Opción B: línea de comandos** (el cliente `mysql` debe estar en el PATH)

```powershell
mysql -u root -p -e "CREATE DATABASE destellos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cmd /c "mysql -u root -p destellos < base_datos\tu_script.sql"
```

> En PowerShell el operador `<` no funciona, por eso la importación se ejecuta con `cmd /c`.
> Cambia `tu_script.sql` por el nombre real de tu archivo.

**Opción C: XAMPP / phpMyAdmin.** Crea la base `destellos` con cotejamiento `utf8mb4_unicode_ci` y usa la
pestaña **Importar** para cargar el script.

### 4.3. Valores que Django necesita

Se leen del archivo `.env` (ver paso 5): `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`. En
`config/settings.py` el motor es `django.db.backends.mysql` con `charset: utf8mb4` y un tiempo máximo de
conexión de 10 segundos, de modo que un error de conexión se muestra rápido en vez de quedarse colgado.

**Seguridad de las credenciales:**

* Escríbelas solo en `.env`; ese archivo está listado en `.gitignore`.
* Nunca pongas contraseñas en `settings.py`, en el README ni en capturas de pantalla.
* Comparte `.env.example` (sin valores reales), nunca `.env`.

### 4.4. Ejecutar y verificar las migraciones

```powershell
python manage.py migrate
python manage.py showmigrations
python manage.py makemigrations --check --dry-run
```

* `showmigrations` debe mostrar todas las migraciones con `[X]`.
* `makemigrations --check --dry-run` debe responder `No changes detected`.

Para verificar la configuración y la conexión:

```powershell
python manage.py check
python manage.py dbshell
```

(`dbshell` requiere el cliente `mysql` en el PATH; sal con `exit`.)

### 4.5. Errores de conexión más comunes

| Mensaje o síntoma | Causa probable | Solución |
| --- | --- | --- |
| `Can't connect to MySQL server on '127.0.0.1'` | MySQL no está iniciado | Inicia el servicio (Servicios de Windows → MySQL80, o el botón *Start* de XAMPP). |
| `Access denied for user 'root'@'localhost'` | Usuario o contraseña incorrectos | Revisa `DB_USER` y `DB_PASSWORD` en `.env`. |
| `Unknown database 'destellos'` | La base de datos no existe | Créala (sección 4.2) o corrige `DB_NAME`. |
| `ModuleNotFoundError: No module named 'MySQLdb'` | `mysqlclient` no está instalado | Activa el entorno virtual y ejecuta `pip install -r requirements.txt`. |
| Falla al instalar `mysqlclient` | No hay un paquete compatible con tu versión de Python | Usa Python 3.12 y actualiza pip: `python -m pip install --upgrade pip`. |
| Conexión rechazada por puerto | MySQL usa otro puerto | Ajusta `DB_PORT` en `.env` (el valor por defecto es `3306`). |
| Tras cambiar `.env` nada cambia | El servidor sigue con la configuración anterior | Detén el servidor con `Ctrl + C` y vuelve a ejecutar `python manage.py runserver`. |

---

## 5. Estructura del proyecto

```text
tienda_destellos/
  manage.py                  Punto de entrada de los comandos de Django
  requirements.txt           Dependencias de Python
  .env.example               Plantilla de variables de entorno (copiar a .env)
  .env                       Variables reales (privado, no se sube a Git)
  .gitignore / .gitattributes
  .vscode/settings.json      Ajustes recomendados para VS Code
  README.md                  Este documento
  config/                    Configuración del proyecto Django
    settings.py              Ajustes (apps, base de datos, seguridad, estáticos)
    settings_test.py         Ajustes para correr las pruebas con SQLite
    urls.py                  Rutas principales (/admin/, /panel/, tienda y cuentas)
    compat.py                Parche de compatibilidad con Python 3.15
    wsgi.py / asgi.py        Puntos de entrada para servidores de producción
  tienda/                    App de la tienda
    models.py                Modelos: Cliente, Producto, Pedido, DetallePedido, Pago, CarritoCliente, PedidoToken
    views.py                 Vistas: inicio, productos, detalle, checkout, pedido confirmado
    api.py                   Endpoints del carrito y del checkout (/api/...)
    carrito.py               Lógica del carrito
    urls.py                  Rutas de la tienda
    context_processors.py    Datos disponibles en todas las plantillas
    templatetags/            Filtros y etiquetas de plantilla
    management/commands/     Comando cargar_productos
    migrations/              Migraciones (0001_initial: tablas del carrito)
    test_runner.py           Ejecutor de pruebas (crea las tablas externas en SQLite)
    tests.py                 Pruebas de la tienda
  cuentas/                   App de autenticación
    views.py / urls.py       Login de clientes y login del personal
    forms.py                 Formularios de inicio de sesión
    backends.py              Autenticación por usuario o correo
    middleware.py            Asocia al cliente con la sesión (request.cliente)
    throttle.py              Bloqueo por intentos fallidos
    grupos.py                Roles base (grupos y permisos)
    tests.py                 Pruebas de cuentas
  panel/                     App del panel administrativo
    views.py / urls.py       Vistas y rutas del panel
    forms.py                 Formularios de productos, pedidos y usuarios
    imagenes.py              Validación y guardado de imágenes
    reglas.py                Reglas de negocio del panel
    tests.py                 Pruebas del panel
  templates/                 Plantillas HTML
    base.html                Estructura común de la tienda
    partials/                navbar, producto_card, cart_drawer
    tienda/                  index, productos, producto_detalle, checkout, pedido_confirmado
    cuentas/                 login, panel_login
    panel/                   base_panel y pantallas de administración
    403.html                 Página de acceso denegado
  static/                    Archivos estáticos
    css/style.css            Estilos globales y tokens de diseño (paleta, radios, sombras, tiempos)
    css/panel.css            Estilos específicos del panel
    js/main.js               Carrusel, menú y comportamientos generales
    js/tienda.js, cart.js    Carrito y página de producto
    js/panel.js              Comportamientos del panel
    img/                     Imágenes y logo (las subidas del panel van a img/productos/, ignorada por Git)
  tests_e2e/                 Pruebas de navegador con Playwright (opcionales)
  venv/                      Entorno virtual (se crea en la instalación; no se sube a Git)
```

---

## 6. Guía de uso

### 6.1. Como cliente

1. **Explorar:** desde el inicio o desde `/productos/`. Usa el buscador del encabezado para filtrar por nombre.
2. **Ver un producto:** haz clic en una tarjeta para abrir su detalle.
3. **Agregar al carrito:** elige la cantidad y pulsa el botón de agregar. El icono de la bolsa muestra la cantidad.
4. **Revisar el carrito:** abre el icono de la bolsa. Puedes cambiar cantidades con **−** y **+**, quitar
   productos o usar **Vaciar carrito** (pide confirmación).
5. **Comprar:** pulsa **Finalizar compra** (`/checkout/`) y confirma el pedido. Verás la página de confirmación.
6. **Cuenta de cliente:** inicia sesión en `/login/` con tu correo y contraseña. Con sesión iniciada, el carrito se
   sincroniza con el servidor. La tienda no tiene formulario de registro público: los clientes existen en la
   tabla `clientes`.

### 6.2. Como personal administrativo

Entra por `/panel/ingresar/`. Lo que ves depende de tus permisos.

| Módulo | Qué puedes hacer |
| --- | --- |
| **Resumen** | Ver indicadores generales (por ejemplo, pedidos pendientes). |
| **Productos** | Buscar, crear, editar y eliminar productos; subir imagen (PNG, JPG o WebP, hasta 2 MB). |
| **Pedidos** | Buscar, filtrar por estado, ver el detalle y cambiar el estado. |
| **Clientes** | Consultar los clientes registrados. |
| **Gestión de usuarios** | Crear usuarios del personal, editarlos, cambiar su contraseña y activarlos o desactivarlos. Solo el administrador (superusuario). |

**Roles:**

* **Administrador** = superusuario de Django: accede a todo, incluida la gestión de usuarios.
* **Usuario administrativo** = cuenta con `is_staff` y uno o más grupos: *Gestor de productos*,
  *Gestor de pedidos* o *Consulta*. Sin grupos no ve ningún módulo. Los permisos de cada grupo se pueden
  ajustar en `/admin/`.
* No existe registro público para el personal: solo un administrador crea cuentas.

**Seguridad ya incluida:** 5 intentos fallidos bloquean el acceso durante 15 minutos (por IP y usuario; aplica al login del personal y también al de clientes, con contadores separados), el cierre de
sesión se hace solo por POST y las cookies son seguras cuando `DEBUG=False`.

### 6.3. Cómo funciona el carrito

* En el navegador se guarda en `localStorage` (clave `destellos.cart.v1`).
* Para clientes con sesión se sincroniza con la tabla `tienda_carritocliente`.
* El servidor decide los precios, totales y existencias (`/api/carrito/validar/` y `/api/checkout/`).
* El pedido se crea en `pedidos` y `detalle_pedidos` dentro de una transacción; `PedidoToken` evita duplicados.
* Límites en `config/settings.py`: `CARRITO_MAX_POR_PRODUCTO = 99` y `CARRITO_MAX_LINEAS = 50`.

---

## 7. Solución de problemas

| Problema | Causa | Solución |
| --- | --- | --- |
| `ModuleNotFoundError: No module named ...` | Falta una dependencia o el entorno virtual no está activo | Activa el entorno (`.\venv\Scripts\Activate.ps1`) y ejecuta `pip install -r requirements.txt`. |
| `No module named django` | Django no está instalado en el Python que usas | Activa el entorno virtual e instala las dependencias. Comprueba con `python -m django --version`. |
| `ERR_CONNECTION_REFUSED` en el navegador | El servidor no está corriendo | Ejecuta `python manage.py runserver` y deja la ventana abierta. Usa `http://127.0.0.1:8000/`. |
| Errores de conexión con MySQL | Servicio apagado o credenciales incorrectas | Consulta la tabla de la [sección 4.5](#45-errores-de-conexión-más-comunes). |
| `You have N unapplied migration(s)` | Faltan migraciones | Ejecuta `python manage.py migrate`. |
| `Table 'destellos.productos' doesn't exist` | No se importó el script SQL original | Importa el script (sección 4.2) y vuelve a intentar. |
| Estilos o imágenes no cargan | Archivos estáticos desactualizados o `DEBUG=False` | En desarrollo, mantén `DEBUG=True` y fuerza la recarga con `Ctrl + F5`. Con `DEBUG=False` ejecuta `python manage.py collectstatic`. |
| La imagen que subí no aparece con `DEBUG=False` | Las imágenes se guardan en `static/img/productos/` | Ejecuta `python manage.py collectstatic` después de subirlas. |
| `TemplateDoesNotExist` o `TemplateSyntaxError` | Plantilla mal escrita o ruta incorrecta | Lee el nombre del archivo y la línea que muestra el error. Las plantillas están en `templates/`. |
| `Error: That port is already in use` | Otro programa usa el puerto 8000 | Usa otro puerto: `python manage.py runserver 8001`. O libera el 8000 (abajo). |
| Cambié `.env` y no se nota | El servidor lee el archivo solo al iniciar | Detén con `Ctrl + C` y vuelve a iniciar. |
| Aparece `dev-inseguro-cambiar` o un `DEBUG` inesperado | `.env` no existe o está en otra carpeta | Debe estar junto a `manage.py` (`Copy-Item .env.example .env`). |
| `CSRF verification failed` | Se accedió desde un host no permitido | Añade el host a `ALLOWED_HOSTS` en `.env`. |
| PowerShell: *la ejecución de scripts está deshabilitada* | Política de ejecución | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y activa de nuevo el entorno. |

**Liberar el puerto 8000 en Windows:**

```powershell
netstat -ano | findstr :8000
taskkill /PID <número_de_PID> /F
```

---

## 8. Mantenimiento y desarrollo

**Iniciar el servidor** (con el entorno virtual activo):

```powershell
python manage.py runserver
```

**Revisar la configuración:**

```powershell
python manage.py check
```

**Ejecutar las pruebas existentes** (105 pruebas de tienda, cuentas y panel):

```powershell
# Con MySQL (el usuario necesita permiso para crear la base "test_destellos"):
python manage.py test

# Sin MySQL, con una base SQLite temporal:
python manage.py test --settings=config.settings_test
```

**Pruebas de navegador (opcionales):**

```powershell
pip install playwright
playwright install chromium
```

Las instrucciones de uso están en la cabecera de `tests_e2e/e2e_playwright.py`.

**Crear migraciones cuando sea necesario:** solo si cambias modelos con `managed = True` (`CarritoCliente`,
`PedidoToken`). Los modelos `managed = False` representan tablas externas: sus cambios se hacen en MySQL, no con
migraciones.

```powershell
python manage.py makemigrations
python manage.py migrate
```

**Mantener las dependencias al día:**

```powershell
pip list --outdated
pip install --upgrade <paquete>
pip freeze > requirements.txt
python manage.py check
python manage.py test --settings=config.settings_test
```

Si actualizas Django, hazlo dentro de la rama LTS compatible con tu base de datos y vuelve a ejecutar las pruebas
antes de publicar.

**Estilos y diseño:** los colores (paleta `#EDE9DE`, `#63635E`, `#E8DFC9`, `#EBE7DB`, `#EEEAE0`), radios, sombras y
duraciones de transición están centralizados como variables CSS al inicio de `static/css/style.css` (bloque
`:root`). Para ajustar el aspecto de toda la tienda, edita esas variables.

**Antes de publicar en producción:**

1. Define una `SECRET_KEY` propia, usa `DEBUG=False` y configura `ALLOWED_HOSTS`.
2. Sirve el sitio por HTTPS y activa `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` y, si hay proxy, `USE_X_FORWARDED_PROTO`.
3. Ejecuta `python manage.py collectstatic` y configura el servidor web para servir `staticfiles/`
   (Django no sirve estáticos con `DEBUG=False`).
4. Revisa con `python manage.py check --deploy`.
5. **Actualiza Django:** la serie 5.0 dejó de recibir parches de seguridad en abril de 2025. Si tu MySQL es 8 o
   MariaDB 10.5 o superior, cambia `requirements.txt` a `Django>=5.2,<5.3` (LTS) y vuelve a ejecutar las pruebas.
6. Con varios procesos del servidor, configura una caché compartida (`CACHES`, p. ej. Redis): el bloqueo de intentos
   de inicio de sesión usa la caché de Django y con la caché por defecto cuenta por proceso.
