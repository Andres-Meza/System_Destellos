/* ==========================================================================
   DESTELLOS · main.js
   Menú móvil, carrusel de inicio y animaciones de entrada (GSAP).
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    /* ---- Menú hamburguesa ---- */
    const menuToggle = document.getElementById("mobile-menu");
    const nav = document.getElementById("primary-nav");
    if (menuToggle && nav) {
        const setMenu = (open) => {
            nav.classList.toggle("is-open", open);
            menuToggle.classList.toggle("is-active", open);
            menuToggle.setAttribute("aria-expanded", String(open));
            menuToggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
        };
        menuToggle.addEventListener("click", () => setMenu(!nav.classList.contains("is-open")));
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && nav.classList.contains("is-open")) { setMenu(false); menuToggle.focus(); }
        });
        document.addEventListener("click", (e) => {
            if (nav.classList.contains("is-open") && !nav.contains(e.target) && !menuToggle.contains(e.target)) setMenu(false);
        });
        window.matchMedia("(min-width: 821px)").addEventListener("change", (m) => { if (m.matches) setMenu(false); });
    }

    /* ---- Carrusel (solo existe en la página de inicio) ---- */
    const carousel = document.getElementById("carousel");
    if (carousel) {
        const track = document.getElementById("carousel-track");
        const total = track.children.length;
        const dotsBox = document.getElementById("carousel-dots");
        const INTERVAL = 4000; // ms entre imágenes

        let index = 0;
        let timer = null;

        const dots = [];
        for (let i = 0; i < total; i++) {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.setAttribute("aria-label", "Ir a la imagen " + (i + 1));
            dot.addEventListener("click", () => { goTo(i); restart(); });
            dotsBox.appendChild(dot);
            dots.push(dot);
        }

        function goTo(i) {
            index = (i + total) % total;
            track.style.transform = "translateX(-" + (index * 100) + "%)";
            dots.forEach((d, n) => {
                d.classList.toggle("active", n === index);
                d.setAttribute("aria-current", n === index ? "true" : "false");
            });
            Array.from(track.children).forEach((s, n) => s.setAttribute("aria-hidden", n === index ? "false" : "true"));
        }

        const start = () => { if (!reduceMotion && !timer) timer = setInterval(() => goTo(index + 1), INTERVAL); };
        const stop = () => { clearInterval(timer); timer = null; };
        const restart = () => { stop(); start(); };

        document.getElementById("carousel-prev").addEventListener("click", () => { goTo(index - 1); restart(); });
        document.getElementById("carousel-next").addEventListener("click", () => { goTo(index + 1); restart(); });

        // Pausa con el mouse, con el foco del teclado y con la pestaña oculta
        carousel.addEventListener("mouseenter", stop);
        carousel.addEventListener("mouseleave", start);
        carousel.addEventListener("focusin", stop);
        carousel.addEventListener("focusout", start);
        document.addEventListener("visibilitychange", () => { document.hidden ? stop() : start(); });

        // Deslizar con el dedo (móvil)
        let startX = 0;
        carousel.addEventListener("touchstart", (e) => { startX = e.touches[0].clientX; stop(); }, { passive: true });
        carousel.addEventListener("touchend", (e) => {
            const diff = e.changedTouches[0].clientX - startX;
            if (Math.abs(diff) > 50) goTo(diff < 0 ? index + 1 : index - 1);
            start();
        });

        goTo(0);
        start();
    }

    /* ---- Animaciones de entrada (GSAP, sutiles y rápidas) ----
       Si GSAP no carga o el usuario prefiere menos movimiento, no se anima nada
       y el contenido se ve igual. Siempre se limpian los estilos al terminar. */
    if (typeof gsap === "undefined" || reduceMotion) return;

    const page = document.body.dataset.page;
    const rise = { y: 16, opacity: 0, duration: 0.55, ease: "power2.out", clearProps: "transform,opacity" };

    if (page === "inicio") {
        gsap.from(".hero > *", { ...rise, stagger: 0.1 });
        if (carousel) gsap.from(carousel, { ...rise, delay: 0.25 });
        gsap.from(".feature", { ...rise, stagger: 0.12, delay: 0.35 });
    } else if (page === "productos") {
        gsap.from(".page-head > *", { ...rise, stagger: 0.08 });
        gsap.from(".p-grid__item", { ...rise, duration: 0.45, stagger: 0.035, delay: 0.1 });
    } else if (page === "producto") {
        gsap.from(".detail__media", { ...rise });
        gsap.from(".detail__info > *", { ...rise, stagger: 0.07, delay: 0.1 });
    } else if (page === "checkout" || page === "pedido" || page === "login") {
        gsap.from(".page-head > *, .panel", { ...rise, stagger: 0.08 });
    }
});
