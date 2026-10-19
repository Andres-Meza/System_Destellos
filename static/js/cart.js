/* ==========================================================================
   DESTELLOS · Núcleo del carrito (sin dependencias, sin DOM)
   - Persistencia: localStorage ("destellos.cart.v1"). Si no está disponible,
     el carrito vive en memoria y la interfaz avisa.
   - Dinero: siempre en centavos enteros (nunca float).
   - Los precios guardados aquí son SOLO para mostrar; el servidor es la
     autoridad: valida/recalcula en /api/carrito/validar/ y en el checkout.
   - Clientes con sesión: sincroniza con la BD (/api/carrito/sync/).
   ========================================================================== */
(function (global) {
  'use strict';

  var KEY = 'destellos.cart.v1';
  var cfg = {};
  try {
    var el = document.getElementById('tienda-config');
    cfg = el ? JSON.parse(el.textContent) : {};
  } catch (e) { cfg = {}; }
  var MAX = cfg.maxQty || 99;
  var URLS = cfg.urls || {};
  var TIMEOUT_MS = 15000;

  /* ---------- Dinero (centavos enteros) ---------- */
  function toCents(str) {
    var m = /^(\d+)(?:\.(\d{1,2}))?\d*$/.exec(String(str).trim());
    if (!m) return 0;
    return parseInt(m[1], 10) * 100 + parseInt(((m[2] || '') + '00').slice(0, 2), 10);
  }
  // Debe coincidir con el filtro `precio` de Django: $1.234 · $8,99
  function fmtCents(c) {
    var neg = c < 0; c = Math.abs(c);
    var ent = Math.floor(c / 100), dec = c % 100;
    var t = String(ent).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    if (dec) t += ',' + (dec < 10 ? '0' : '') + dec;
    return (neg ? '-' : '') + '$' + t;
  }

  /* ---------- Estado ---------- */
  function emptyState() {
    return { v: 1, items: {}, owner: null, dirty: false, base: null, rev: 0, ts: 0 };
  }
  function isInt(n) { return typeof n === 'number' && isFinite(n) && Math.floor(n) === n; }
  function safePath(s) { return typeof s === 'string' && /^\/(?![\/\\])/.test(s) ? s : ''; }

  // Valida TODO lo leído de localStorage (puede haber sido manipulado o estar corrupto).
  function sanitize(raw) {
    var st = emptyState();
    if (!raw || typeof raw !== 'object') return st;
    if (isInt(raw.owner) && raw.owner > 0) st.owner = raw.owner;
    st.dirty = !!raw.dirty;
    if (isInt(raw.base) && raw.base >= 0) st.base = raw.base;
    if (isInt(raw.rev) && raw.rev >= 0) st.rev = raw.rev;
    if (isInt(raw.ts) && raw.ts >= 0) st.ts = raw.ts;
    var items = raw.items && typeof raw.items === 'object' ? raw.items : {};
    Object.keys(items).forEach(function (id) {
      var it = items[id];
      if (!/^\d+$/.test(id) || !it || typeof it !== 'object') return;
      var q = parseInt(it.q, 10);
      if (!(q >= 1)) return;
      var p = String(it.p || '');
      st.items[id] = {
        q: Math.min(q, MAX),
        n: String(it.n || 'Producto').slice(0, 120),
        p: /^\d+(\.\d{1,2})?$/.test(p) ? p : '0.00',
        i: safePath(it.i),
        u: safePath(it.u)
      };
    });
    return st;
  }

  var storageOk = (function () {
    try { var k = '__destellos_t'; localStorage.setItem(k, '1'); localStorage.removeItem(k); return true; }
    catch (e) { return false; }
  })();
  var memory = null;

  function read() {
    if (!storageOk) return memory || (memory = emptyState());
    try {
      var raw = localStorage.getItem(KEY);
      return sanitize(raw ? JSON.parse(raw) : null);
    } catch (e) { return emptyState(); }
  }
  function write(st) {
    if (!storageOk) { memory = st; return; }
    try { localStorage.setItem(KEY, JSON.stringify(st)); }
    catch (e) { storageOk = false; memory = st; emit('storage-error'); }
  }

  /* ---------- Suscripciones ---------- */
  var listeners = [];
  function subscribe(fn) { listeners.push(fn); }
  function emit(type) {
    listeners.slice().forEach(function (fn) { try { fn(type); } catch (e) { /* un oyente no rompe a los demás */ } });
  }
  // Cambios hechos en OTRA pestaña
  window.addEventListener('storage', function (e) { if (e.key === KEY) emit('external'); });

  /* ---------- Lectura ---------- */
  function lines() {
    var st = read();
    return Object.keys(st.items).map(function (id) {
      var it = st.items[id];
      return { id: parseInt(id, 10), q: it.q, n: it.n, p: it.p, i: it.i, u: it.u,
               subCents: toCents(it.p) * it.q };
    });
  }
  function count() { return lines().reduce(function (a, l) { return a + l.q; }, 0); }
  function totalCents() { return lines().reduce(function (a, l) { return a + l.subCents; }, 0); }
  function qtyOf(id) { var it = read().items[String(id)]; return it ? it.q : 0; }
  function toList(st) {
    st = st || read();
    return Object.keys(st.items).map(function (id) { return { id: parseInt(id, 10), qty: st.items[id].q }; });
  }

  /* ---------- Escritura ---------- */
  function mutate(fn) {
    var st = read();
    var result = fn(st);
    st.rev++; st.dirty = true;
    write(st);
    emit('change');
    scheduleSync();
    return result;
  }
  function toQty(q) {
    q = typeof q === 'string' && /^\d+$/.test(q) ? parseInt(q, 10) : q;
    return isInt(q) && q >= 1 ? q : 0;
  }

  // Si el producto ya está, SUMA a su línea (no duplica la línea).
  function add(prod, qty) {
    qty = toQty(qty);
    if (!qty || !prod || !isInt(prod.id)) return { ok: false, reason: 'invalid' };
    return mutate(function (st) {
      var id = String(prod.id), cur = st.items[id], before = cur ? cur.q : 0;
      var q = Math.min(MAX, before + qty);
      st.items[id] = { q: q, n: String(prod.nombre || 'Producto'), p: String(prod.precio || '0.00'),
                       i: safePath(prod.imagen), u: safePath(prod.url) };
      return { ok: true, qty: q, added: q - before, capped: before + qty > MAX };
    });
  }
  function setQty(id, q) {
    q = toQty(q);
    if (!q) return { ok: false, reason: 'invalid' };
    return mutate(function (st) {
      var it = st.items[String(id)];
      if (!it) return { ok: false, reason: 'missing' };
      it.q = Math.min(MAX, q);
      return { ok: true, qty: it.q, capped: q > MAX };
    });
  }
  function remove(id) { mutate(function (st) { delete st.items[String(id)]; }); }
  function clear() { mutate(function (st) { st.items = {}; }); }

  // Vacía por completo el estado local (p. ej. al cerrar sesión).
  function reset() { write(emptyState()); emit('change'); }

  // Tras una compra confirmada: resta SOLO lo comprado (conserva el resto).
  function consume(compradas, version) {
    var st = read();
    (compradas || []).forEach(function (l) {
      var it = st.items[String(l.id)];
      if (!it) return;
      it.q -= l.qty;
      if (it.q <= 0) delete st.items[String(l.id)];
    });
    st.rev++;
    if (isInt(version)) st.base = version;   // el servidor ya descontó lo mismo
    write(st);
    emit('change');
    scheduleSync();
  }

  /* ---------- Red ---------- */
  function post(url, body) {
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS) : null;
    return fetch(url, {
      method: 'POST', credentials: 'same-origin', signal: ctrl ? ctrl.signal : undefined,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf || '', 'X-Requested-With': 'fetch' },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (d) {
        return { status: r.status, ok: r.ok, data: d };
      });
    }).then(function (res) { if (timer) clearTimeout(timer); return res; },
            function (err) { if (timer) clearTimeout(timer); throw err; });
  }

  /* ---------- Validación con el servidor (precios oficiales) ---------- */
  // Actualiza nombre/precio/imagen locales con los oficiales, recorta cantidades
  // excesivas y retira productos que ya no existen. Si el usuario cambió el
  // carrito mientras tanto, no pisa sus cambios.
  function validate() {
    var sent = read();
    if (!sent.items || !Object.keys(sent.items).length) {
      return Promise.resolve({ ok: true, lineas: [], no_disponibles: [], total: '0.00', unidades: 0 });
    }
    return post(URLS.validar, { items: toList(sent) }).then(function (res) {
      if (!res.ok || !res.data || !res.data.ok) {
        var e = new Error('validate'); e.status = res.status; e.data = res.data; throw e;
      }
      var data = res.data, cur = read();
      if (cur.rev === sent.rev) {
        var changed = false;
        (data.no_disponibles || []).forEach(function (id) {
          if (cur.items[String(id)]) { delete cur.items[String(id)]; changed = true; }
        });
        data.lineas.forEach(function (l) {
          var it = cur.items[String(l.id)];
          if (!it) return;
          if (it.q !== l.qty) { it.q = l.qty; changed = true; }
          it.n = l.nombre; it.p = l.precio; it.i = safePath(l.imagen); it.u = safePath(l.url);
        });
        if (changed) { cur.rev++; cur.dirty = true; }
        write(cur);
        emit(changed ? 'change' : 'refreshed');
        if (changed) scheduleSync();
      }
      return data;
    });
  }

  /* ---------- Sincronización con la BD (solo clientes con sesión) ---------- */
  var syncTimer = null, syncing = false, pendingSync = false;

  function scheduleSync(delay) {
    if (!cfg.clienteId) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(sync, delay == null ? 700 : delay);
  }

  function adopt(cur, data) {
    var items = {};
    data.lineas.forEach(function (l) {
      items[String(l.id)] = { q: l.qty, n: l.nombre, p: l.precio, i: safePath(l.imagen), u: safePath(l.url) };
    });
    cur.items = items;
    cur.owner = data.owner;
    cur.dirty = false;
    cur.base = data.version;
    cur.ts = Date.now();
    cur.rev++;
    write(cur);
    emit('synced');
  }

  function sync(opts) {
    if (!cfg.clienteId) return Promise.resolve({ skipped: 'anonimo' });
    if (!navigator.onLine) return Promise.resolve({ skipped: 'sin-conexion' });
    if (syncing) { pendingSync = true; return Promise.resolve({ skipped: 'ocupado' }); }
    var sent = read();
    // Evita una petición en cada navegación si ya está sincronizado hace poco.
    if (!(opts && opts.force) && !sent.dirty && sent.owner === cfg.clienteId && Date.now() - sent.ts < 30000) {
      return Promise.resolve({ skipped: 'reciente' });
    }
    syncing = true;
    return post(URLS.sync, { items: toList(sent), owner: sent.owner, dirty: sent.dirty, base: sent.base })
      .then(function (res) {
        if (res.status === 401) { emit('auth-expired'); return { skipped: 'sesion' }; }
        if (!res.ok || !res.data || !res.data.ok) throw new Error('http ' + res.status);
        var cur = read();
        if (cur.rev !== sent.rev) { pendingSync = true; return { skipped: 'cambio-local' }; }
        adopt(cur, res.data);
        return { ok: true, accion: res.data.accion };
      })
      .catch(function () { emit('sync-error'); return { error: true }; })
      .then(function (r) {
        syncing = false;
        if (pendingSync) { pendingSync = false; scheduleSync(300); }
        return r;
      });
  }

  // Al recuperar la conexión, reanuda la sincronización.
  window.addEventListener('online', function () { emit('online'); scheduleSync(0); });
  window.addEventListener('offline', function () { emit('offline'); });

  // Sincronización inicial al cargar cada página (si hay sesión).
  if (cfg.clienteId) scheduleSync(0);

  global.DestellosCart = {
    cfg: cfg, MAX: MAX, urls: URLS,
    fmt: fmtCents, toCents: toCents,
    lines: lines, count: count, totalCents: totalCents, qtyOf: qtyOf, toList: toList,
    add: add, setQty: setQty, remove: remove, clear: clear, reset: reset, consume: consume,
    validate: validate, sync: sync, post: post, subscribe: subscribe,
    storageOk: function () { return storageOk; },
    isLoggedIn: function () { return !!cfg.clienteId; },
    ownedByUser: function () { return read().owner !== null; }
  };
})(window);
