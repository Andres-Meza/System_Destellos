/* ==========================================================================
   DESTELLOS · Interfaz de tienda (panel del carrito, detalle, checkout)
   Depende de cart.js (window.DestellosCart). Usa GSAP solo si está cargado y
   el usuario no pidió movimiento reducido; sin GSAP todo funciona igual.
   Todo texto dinámico se inserta con textContent (nunca innerHTML).
   ========================================================================== */
(function () {
  'use strict';
  var Cart = window.DestellosCart;
  if (!Cart) return;

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function anim() { return typeof window.gsap !== 'undefined' && !reduce; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function plural(n, s, p) { return n === 1 ? s : p; }

  var cartBtn = $('#cart-open'), badge = $('#cart-badge');
  var drawer = $('#cart-drawer'), overlay = $('#cart-overlay');
  var body = $('#cart-body'), foot = $('#cart-foot'), notice = $('#cart-notice');
  var totalEl = $('#cart-total'), totalNote = $('#cart-total-note');
  var isOpen = false, lastFocus = null, animToken = 0;
  var validation = { state: 'idle' };   // idle | loading | ok | fail
  var focusAfter = null;

  /* ---------- Avisos (toast) ---------- */
  function toast(msg, opts) {
    opts = opts || {};
    var region = $('#toast-region');
    if (!region) return;
    var t = el('div', 'toast' + (opts.error ? ' toast--error' : ''));
    t.appendChild(el('span', null, msg));
    if (opts.action) {
      var b = el('button', null, opts.action.label);
      b.type = 'button';
      b.addEventListener('click', function () { opts.action.fn(); remove(); });
      t.appendChild(b);
    }
    region.appendChild(t);
    if (anim()) window.gsap.from(t, { y: 14, opacity: 0, duration: 0.3, ease: 'power2.out' });
    var timer = setTimeout(remove, opts.error ? 6000 : 4000);
    function remove() {
      clearTimeout(timer);
      if (!t.parentNode) return;
      if (anim()) window.gsap.to(t, { opacity: 0, y: 8, duration: 0.2, onComplete: function () { t.remove(); } });
      else t.remove();
    }
  }

  /* ---------- Indicador del header ---------- */
  var lastCount = null;
  function updateBadge() {
    var n = Cart.count();
    if (!badge || !cartBtn) return;
    badge.textContent = n > 99 ? '99+' : String(n);
    badge.hidden = n === 0;
    cartBtn.setAttribute('aria-label', n ? 'Abrir carrito, ' + n + ' ' + plural(n, 'artículo', 'artículos') : 'Abrir carrito, vacío');
    if (lastCount !== null && n !== lastCount && n > 0 && anim()) {
      window.gsap.fromTo(badge, { scale: 1.5 }, { scale: 1, duration: 0.4, ease: 'back.out(2)', clearProps: 'transform' });
    }
    lastCount = n;
  }

  /* ---------- Conexión ---------- */
  var offlineBar = null;
  function updateOnline() {
    var off = !navigator.onLine;
    if (off && !offlineBar) {
      offlineBar = el('div', 'offline-bar', 'Sin conexión: tu carrito se guarda en este dispositivo y se sincronizará al reconectar.');
      offlineBar.setAttribute('role', 'status');
      document.body.insertBefore(offlineBar, document.body.firstChild);
    } else if (!off && offlineBar) {
      offlineBar.remove(); offlineBar = null;
    }
    if (isOpen) renderNotice();
  }

  /* ---------- Panel del carrito ---------- */
  function renderNotice() {
    notice.textContent = '';
    var msgs = [];
    if (!Cart.storageOk()) msgs.push('Tu navegador bloquea el almacenamiento local: el carrito no se conservará al recargar o cambiar de página.');
    if (!navigator.onLine) msgs.push('Sin conexión: puedes ver y editar tu carrito. Para finalizar la compra necesitas conexión.');
    if (validation.state === 'fail' && navigator.onLine) msgs.push('No pudimos verificar los precios ahora; se confirmarán al finalizar la compra.');
    if (validation.removed) msgs.push(validation.removed);
    msgs.forEach(function (m) { notice.appendChild(el('p', null, m)); });
    notice.hidden = msgs.length === 0;
  }

  function placeholderIcon() {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('width', '28'); s.setAttribute('height', '28');
    s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '1.2');
    s.setAttribute('aria-hidden', 'true');
    s.innerHTML = '<rect x="3.5" y="4.5" width="17" height="15" rx="1"/><circle cx="9" cy="10" r="1.6"/><path d="m4 18 5.2-5 3.5 3.3 2.8-2.6L20 17"/>';
    return s;
  }
  function thumb(l, cls) {
    var w = el('div', cls);
    if (l.i) {
      var img = el('img'); img.src = l.i; img.alt = ''; img.width = 76; img.height = 76; img.loading = 'lazy';
      img.addEventListener('error', function () { img.remove(); w.appendChild(placeholderIcon()); });
      w.appendChild(img);
    } else w.appendChild(placeholderIcon());
    return w;
  }

  function lineEl(l) {
    var li = el('li', 'cart-line'); li.dataset.line = l.id;
    li.appendChild(thumb(l, 'cart-line__img'));
    var info = el('div');
    var name = el('a', 'cart-line__name', l.n); name.href = l.u || '#';
    info.appendChild(name);
    info.appendChild(el('p', 'cart-line__unit', Cart.fmt(Cart.toCents(l.p)) + ' c/u'));

    var row = el('div', 'cart-line__row');
    var st = el('div', 'stepper'); st.setAttribute('role', 'group'); st.setAttribute('aria-label', 'Cantidad de ' + l.n);
    var dec = el('button', 'stepper__btn', '\u2212'); dec.type = 'button'; dec.dataset.act = 'dec'; dec.dataset.id = l.id;
    dec.setAttribute('aria-label', 'Disminuir cantidad de ' + l.n); dec.disabled = l.q <= 1;
    var inp = el('input'); inp.type = 'text'; inp.inputMode = 'numeric'; inp.value = String(l.q); inp.autocomplete = 'off';
    inp.dataset.act = 'qty'; inp.dataset.id = l.id; inp.setAttribute('aria-label', 'Cantidad de ' + l.n);
    var inc = el('button', 'stepper__btn', '+'); inc.type = 'button'; inc.dataset.act = 'inc'; inc.dataset.id = l.id;
    inc.setAttribute('aria-label', 'Aumentar cantidad de ' + l.n); inc.disabled = l.q >= Cart.MAX;
    st.appendChild(dec); st.appendChild(inp); st.appendChild(inc);
    row.appendChild(st);
    row.appendChild(el('span', 'cart-line__sub', Cart.fmt(l.subCents)));
    info.appendChild(row);

    var rm = el('button', 'link-btn cart-line__remove', 'Eliminar'); rm.type = 'button';
    rm.dataset.act = 'remove'; rm.dataset.id = l.id; rm.setAttribute('aria-label', 'Eliminar ' + l.n + ' del carrito');
    info.appendChild(rm);
    li.appendChild(info);
    return li;
  }

  function render() {
    var ls = Cart.lines();
    body.textContent = '';
    if (!ls.length) {
      var empty = el('div', 'cart-empty');
      empty.appendChild(el('h3', null, 'Tu carrito está vacío'));
      empty.appendChild(el('p', null, 'Explora el catálogo y agrega tus decoraciones favoritas.'));
      var a = el('a', 'btn btn--primary', 'Ver productos'); a.href = Cart.urls.productos || '/productos/';
      empty.appendChild(a);
      body.appendChild(empty);
      foot.hidden = true;
    } else {
      var ul = el('ul', 'cart-lines');
      ls.forEach(function (l) { ul.appendChild(lineEl(l)); });
      body.appendChild(ul);
      foot.hidden = false;
      totalEl.textContent = Cart.fmt(Cart.totalCents());
      totalNote.textContent =
        validation.state === 'loading' ? 'Verificando precios…' :
        validation.state === 'ok' ? 'Precios verificados con el servidor.' :
        'Los precios se confirman al finalizar la compra.';
    }
    $('#cart-title').textContent = ls.length ? 'Tu carrito (' + Cart.count() + ')' : 'Tu carrito';
    renderNotice();
    restoreFocus();
  }

  function restoreFocus() {
    if (!focusAfter || !isOpen) { focusAfter = null; return; }
    var t = $('[data-line="' + focusAfter.id + '"] [data-act="' + focusAfter.act + '"]', body);
    if (t && !t.disabled) t.focus();
    else {
      var any = $('.cart-line [data-act="remove"]', body) || $('#cart-continue') || $('#cart-close');
      if (any) any.focus();
    }
    focusAfter = null;
  }

  function verify() {
    if (!navigator.onLine || !Cart.lines().length) return;
    validation = { state: 'loading' };
    render();
    var before = Cart.lines().map(function (l) { return l.id; });
    Cart.validate().then(function () {
      var after = Cart.lines().map(function (l) { return l.id; });
      var gone = before.length - after.length;
      validation = { state: 'ok', removed: gone > 0 ? (gone + ' ' + plural(gone, 'producto ya no está disponible y se quitó', 'productos ya no están disponibles y se quitaron') + ' del carrito.') : '' };
      render();
    }).catch(function () { validation = { state: 'fail' }; render(); });
  }

  var inertEls = [];
  function setInert(on) {
    if (on) {
      inertEls = ['.site-header', 'main', '.site-footer'].map(function (s) { return $(s); }).filter(Boolean);
      inertEls.forEach(function (n) { n.setAttribute('inert', ''); });
    } else { inertEls.forEach(function (n) { n.removeAttribute('inert'); }); inertEls = []; }
  }

  function openDrawer() {
    if (isOpen) return;
    isOpen = true; lastFocus = document.activeElement;
    var tr = $('#toast-region'); if (tr) tr.textContent = '';   // los avisos no deben tapar el panel
    validation = { state: 'idle' };
    render();
    drawer.hidden = false; overlay.hidden = false;
    document.body.classList.add('drawer-open');
    setInert(true);
    cartBtn.setAttribute('aria-expanded', 'true');
    animToken++;   // invalida el cierre animado que siga en curso
    if (anim()) {
      window.gsap.killTweensOf([drawer, overlay]);
      window.gsap.fromTo(drawer, { xPercent: 100 }, { xPercent: 0, duration: 0.35, ease: 'power3.out', clearProps: 'transform' });
      window.gsap.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: 0.25, clearProps: 'opacity' });
    }
    drawer.focus();
    verify();
  }

  function closeDrawer() {
    if (!isOpen) return;
    isOpen = false;
    var tk = ++animToken;
    var clearConfirm = $('#cart-clear-confirm'); if (clearConfirm) clearConfirm.hidden = true;
    $('#cart-clear').hidden = false;
    function finish() {
      if (tk !== animToken) return;   // se reabrió durante la animación
      drawer.hidden = true; overlay.hidden = true;
      if (anim()) window.gsap.set([drawer, overlay], { clearProps: 'all' });
    }
    document.body.classList.remove('drawer-open');
    setInert(false);
    cartBtn.setAttribute('aria-expanded', 'false');
    if (anim()) {
      window.gsap.killTweensOf([drawer, overlay]);
      window.gsap.to(drawer, { xPercent: 100, duration: 0.25, ease: 'power2.in', onComplete: finish });
      window.gsap.to(overlay, { opacity: 0, duration: 0.2 });
    } else finish();
    if (lastFocus && lastFocus.focus) lastFocus.focus(); else cartBtn.focus();
  }

  function trapTab(e) {
    if (e.key !== 'Tab') return;
    var f = Array.prototype.filter.call(
      drawer.querySelectorAll('a[href], button:not([disabled]), input:not([disabled])'),
      function (n) { return n.offsetParent !== null; });
    if (!f.length) { e.preventDefault(); drawer.focus(); return; }
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === drawer)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function lineMessage(id, text) {
    var li = $('[data-line="' + id + '"]', body);
    if (!li) return;
    var old = $('.cart-line__warn', li); if (old) old.remove();
    if (!text) return;
    var w = el('p', 'cart-line__warn', text); w.setAttribute('role', 'alert');
    li.lastElementChild.appendChild(w);
  }

  if (drawer && cartBtn) {
    cartBtn.setAttribute('aria-expanded', 'false');
    cartBtn.addEventListener('click', openDrawer);
    $('#cart-close').addEventListener('click', closeDrawer);
    $('#cart-continue').addEventListener('click', closeDrawer);
    overlay.addEventListener('click', closeDrawer);
    drawer.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); closeDrawer(); } else trapTab(e);
    });

    body.addEventListener('click', function (e) {
      var b = e.target.closest('[data-act]');
      if (!b || b.tagName === 'INPUT') return;
      var id = parseInt(b.dataset.id, 10), act = b.dataset.act;
      var cur = Cart.lines().filter(function (l) { return l.id === id; })[0];
      if (!cur) return;
      focusAfter = { id: id, act: act };
      if (act === 'inc') {
        if (cur.q >= Cart.MAX) { lineMessage(id, 'Máximo ' + Cart.MAX + ' por producto.'); return; }
        Cart.setQty(id, cur.q + 1);
      } else if (act === 'dec') {
        if (cur.q > 1) Cart.setQty(id, cur.q - 1);
      } else if (act === 'remove') {
        Cart.remove(id);
        toast('Se eliminó «' + cur.n + '» del carrito.');
      }
    });
    body.addEventListener('change', function (e) {
      var inp = e.target;
      if (!inp.dataset || inp.dataset.act !== 'qty') return;
      var id = parseInt(inp.dataset.id, 10), raw = inp.value.trim();
      focusAfter = { id: id, act: 'qty' };
      if (!/^\d+$/.test(raw) || parseInt(raw, 10) < 1) {
        render();
        lineMessage(id, 'Escribe un número entero de 1 a ' + Cart.MAX + '.');
        return;
      }
      var n = parseInt(raw, 10);
      var r = Cart.setQty(id, n);
      if (r && r.capped) setTimeout(function () { lineMessage(id, 'Máximo ' + Cart.MAX + ' por producto.'); }, 0);
    });

    // Vaciar con confirmación en línea (no usa window.confirm)
    $('#cart-clear').addEventListener('click', function () {
      this.hidden = true; $('#cart-clear-confirm').hidden = false; $('#cart-clear-no').focus();
    });
    $('#cart-clear-no').addEventListener('click', function () {
      $('#cart-clear-confirm').hidden = true; $('#cart-clear').hidden = false; $('#cart-clear').focus();
    });
    $('#cart-clear-yes').addEventListener('click', function () {
      Cart.clear();
      $('#cart-clear-confirm').hidden = true; $('#cart-clear').hidden = false;
      toast('Carrito vaciado.');
    });

    // Finalizar compra necesita conexión
    $('#cart-checkout').addEventListener('click', function (e) {
      if (!navigator.onLine) {
        e.preventDefault();
        validation = { state: 'fail' };
        renderNotice();
        toast('Necesitas conexión a internet para finalizar la compra.', { error: true });
      }
    });
  }

  Cart.subscribe(function (type) {
    updateBadge();
    if (type === 'online' || type === 'offline') updateOnline();
    if (isOpen && type !== 'refreshed') render();
    if (type === 'storage-error') toast('No se pudo guardar el carrito en este navegador.', { error: true });
    if (type === 'auth-expired') toast('Tu sesión expiró. Inicia sesión de nuevo para sincronizar tu carrito.', { error: true });
  });
  window.addEventListener('online', updateOnline);
  window.addEventListener('offline', updateOnline);
  updateBadge(); updateOnline();
  if (!Cart.storageOk()) toast('Tu navegador bloquea el almacenamiento local: el carrito no se conservará al recargar.', { error: true });

  /* ---------- Cerrar sesión: sincroniza y limpia el carrito local de esa cuenta ---------- */
  var logoutForm = $('form[data-logout]');
  if (logoutForm) {
    logoutForm.addEventListener('submit', function (e) {
      if (!Cart.ownedByUser()) return;           // carrito anónimo: se conserva
      e.preventDefault();
      var done = false;
      function go() { if (done) return; done = true; Cart.reset(); logoutForm.submit(); }
      setTimeout(go, 1500);                      // no bloquear el cierre de sesión
      Cart.sync({ force: true }).then(go, go);
    });
  }

  /* ---------- Imágenes rotas -> marcador neutro ---------- */
  document.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t.tagName === 'IMG' && t.hasAttribute('data-fallback')) {
      var box = t.closest('.p-card__media, .detail__media');
      if (box) box.classList.add('is-empty');
    }
  }, true);
  // Imágenes que fallaron antes de registrar el listener
  Array.prototype.forEach.call(document.querySelectorAll('img[data-fallback]'), function (img) {
    if (img.complete && img.naturalWidth === 0) {
      var box = img.closest('.p-card__media, .detail__media'); if (box) box.classList.add('is-empty');
    }
  });

  /* ==========================================================================
     Página: detalle de producto
     ========================================================================== */
  var form = $('#add-form');
  if (form) {
    var input = $('#qty'), err = $('#qty-error'), addBtn = $('#add-btn'), note = $('#in-cart-note');
    var decB = form.querySelector('[data-step="-1"]'), incB = form.querySelector('[data-step="1"]');
    var max = parseInt(form.dataset.max, 10) || Cart.MAX;
    var current = 1, lastSubmit = 0, doneTimer = null;

    var showErr = function (m) { err.textContent = m || ''; err.hidden = !m; input.setAttribute('aria-invalid', m ? 'true' : 'false'); };
    var sync = function () { decB.disabled = current <= 1; incB.disabled = current >= max; };
    var setQ = function (n) { current = n; input.value = String(n); sync(); };
    var updateNote = function () {
      var n = Cart.qtyOf(form.dataset.id);
      note.hidden = n === 0;
      note.textContent = n ? 'Ya tienes ' + n + ' ' + plural(n, 'unidad', 'unidades') + ' en tu carrito.' : '';
    };
    setQ(1); updateNote();
    Cart.subscribe(updateNote);

    form.querySelectorAll('.stepper__btn').forEach(function (b) {
      b.addEventListener('click', function () {
        var n = current + parseInt(b.dataset.step, 10);
        if (n < 1) { showErr('La cantidad mínima es 1.'); return; }
        if (n > max) { showErr('La cantidad máxima es ' + max + '.'); return; }
        showErr(''); setQ(n);
      });
    });

    input.addEventListener('input', function () {
      var raw = input.value, digits = raw.replace(/\D+/g, '');
      showErr(raw !== digits ? 'Solo se permiten números enteros, sin signos ni decimales.' : '');
      if (digits === '') { input.value = ''; return; }
      var n = parseInt(digits, 10);
      if (n > max) { n = max; showErr('La cantidad máxima es ' + max + '.'); }
      else if (n < 1) { n = 1; showErr('La cantidad mínima es 1.'); }
      setQ(n);
    });
    input.addEventListener('blur', function () { if (input.value === '') { setQ(1); } });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (Date.now() - lastSubmit < 400) return;       // evita doble clic accidental
      if (!/^\d+$/.test(input.value) || current < 1 || current > max) {
        showErr('Escribe un número entero entre 1 y ' + max + '.'); input.focus(); return;
      }
      lastSubmit = Date.now();
      var r = Cart.add({ id: parseInt(form.dataset.id, 10), nombre: form.dataset.nombre,
                         precio: form.dataset.precio, imagen: form.dataset.imagen, url: form.dataset.url }, current);
      if (!r || !r.ok) { showErr('No se pudo agregar el producto.'); return; }
      showErr('');
      if (r.added === 0) {
        toast('Ya tienes el máximo (' + Cart.MAX + ') de este producto en el carrito.', { error: true });
        return;
      }
      toast('Agregado: ' + form.dataset.nombre + ' × ' + r.added + (r.capped ? ' (máximo alcanzado)' : ''),
            { action: { label: 'Ver carrito', fn: openDrawer } });
      addBtn.textContent = 'Agregado ✓'; addBtn.classList.add('is-done');
      clearTimeout(doneTimer);
      doneTimer = setTimeout(function () { addBtn.textContent = 'Agregar al carrito'; addBtn.classList.remove('is-done'); }, 1600);
      setQ(1);
    });
  }

  /* ==========================================================================
     Página: checkout (el servidor valida y crea el pedido)
     ========================================================================== */
  var coLines = $('#co-lines');
  if (coLines) {
    var coTotal = $('#co-total'), coBtn = $('#co-confirm'), coStatus = $('#co-status');
    var reviewed = null;        // respuesta oficial del servidor que el usuario está viendo
    var busy = false, refreshTimer = null;

    var TOKEN_KEY = 'destellos.checkout.token';
    function newToken() {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0; return (c === 'x' ? r : (r & 3 | 8)).toString(16);
      });
    }
    function getToken() {
      try { var t = sessionStorage.getItem(TOKEN_KEY); if (!t) { t = newToken(); sessionStorage.setItem(TOKEN_KEY, t); } return t; }
      catch (e) { return newToken(); }
    }
    function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* nada */ } }

    var status = function (m) { coStatus.textContent = m || ''; };

    function renderReview(data) {
      reviewed = data;
      coLines.textContent = '';
      if (!data.lineas.length) {
        coLines.appendChild(el('p', null, 'Tu carrito está vacío.'));
        var a = el('a', 'btn btn--primary', 'Ver productos'); a.href = Cart.urls.productos; a.style.marginTop = '1rem';
        coLines.appendChild(a);
        coTotal.textContent = '—'; coBtn.disabled = true; return;
      }
      var ul = el('ul', 'order-lines');
      data.lineas.forEach(function (l) {
        var li = el('li');
        li.appendChild(thumb({ i: l.imagen || '' }, 'thumb'));
        var mid = el('div');
        var nm = el('span', 'order-lines__name', l.nombre);
        mid.appendChild(nm);
        mid.appendChild(el('span', 'muted', ' × ' + l.qty + ' · ' + Cart.fmt(Cart.toCents(l.precio)) + ' c/u'));
        li.appendChild(mid);
        li.appendChild(el('span', null, Cart.fmt(Cart.toCents(l.subtotal))));
        ul.appendChild(li);
      });
      coLines.appendChild(ul);
      coTotal.textContent = Cart.fmt(Cart.toCents(data.total));
      coBtn.disabled = busy || !navigator.onLine;
    }

    function refresh(msg) {
      if (!navigator.onLine) {
        coBtn.disabled = true;
        status('Sin conexión: necesitas conexión a internet para confirmar el pedido. Tu carrito está a salvo.');
        return Promise.resolve();
      }
      status(msg || 'Verificando tu carrito…');
      coBtn.disabled = true;
      return Cart.validate().then(function (data) {
        renderReview(data);
        if (!msg) status('');
        if (!navigator.onLine) coBtn.disabled = true;
      }).catch(function () {
        coBtn.disabled = true;
        status('No pudimos verificar tu carrito. Revisa tu conexión e inténtalo de nuevo.');
      });
    }

    function confirmOrder() {
      if (busy || !reviewed || !reviewed.lineas.length) return;
      if (!navigator.onLine) { status('Sin conexión: no se puede confirmar el pedido ahora.'); return; }
      busy = true; coBtn.disabled = true; coBtn.textContent = 'Registrando…';
      status('Registrando tu pedido…');
      var items = reviewed.lineas.map(function (l) { return { id: l.id, qty: l.qty }; });
      Cart.post(Cart.cfg.urls.checkout, { token: getToken(), items: items, total_visto: reviewed.total })
        .then(function (res) {
          var d = res.data;
          if (res.ok && d && d.ok) {
            Cart.consume(d.lineas, d.carrito_version);
            clearToken();
            status('Pedido #' + d.id_pedido + ' registrado. Redirigiendo…');
            window.location.assign(d.url);
            return;
          }
          // Nada de esto es una compra exitosa
          if (res.status === 401) {
            status('Tu sesión expiró. Inicia sesión para continuar; tu carrito se conserva.');
            var lk = el('a', 'link-btn', 'Iniciar sesión'); lk.href = (Cart.urls.login || '/login/') + '?next=' + encodeURIComponent('/checkout/');
            coStatus.appendChild(document.createTextNode(' ')); coStatus.appendChild(lk);
          } else if (res.status === 409 && d && (d.codigo === 'precio_cambiado' || d.codigo === 'productos_no_disponibles')) {
            return refresh(d.mensaje || 'Tu carrito cambió. Revisa el resumen y confirma de nuevo.');
          } else if (d && d.mensaje) {
            status(d.mensaje);
          } else {
            status('No pudimos registrar tu pedido (error ' + res.status + '). Tu carrito sigue intacto; puedes reintentar.');
          }
        })
        .catch(function () {
          // Sin respuesta: puede que el servidor sí lo haya creado. El mismo token evita duplicados al reintentar.
          status('No recibimos confirmación del servidor. Tu carrito sigue intacto. Puedes reintentar: no se duplicará el pedido.');
        })
        .then(function () {
          busy = false; coBtn.textContent = 'Confirmar pedido';
          if (reviewed && reviewed.lineas.length && navigator.onLine) coBtn.disabled = false;
        });
    }

    coBtn.addEventListener('click', confirmOrder);
    Cart.subscribe(function (type) {
      if (busy || type === 'refreshed' || type === 'synced') return;
      if (type === 'online') { refresh(); return; }
      if (type === 'offline') { coBtn.disabled = true; status('Sin conexión: necesitas conexión a internet para confirmar el pedido. Tu carrito está a salvo.'); return; }
      // El carrito cambió (panel u otra pestaña): se vuelve a revisar
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(function () { refresh(); }, 250);
    });
    refresh();
  }

  window.DestellosUI = { toast: toast, openCart: openDrawer, closeCart: closeDrawer };
})();
