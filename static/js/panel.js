/* ==========================================================================
   DESTELLOS · panel.js
   Mejoras de uso (nada de esto protege datos: la seguridad está en el servidor).
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  /* ---- Mostrar / ocultar contraseña (accesible con teclado) ---- */
  document.querySelectorAll('input[type="password"]').forEach((input) => {
    const envoltura = document.createElement("div");
    envoltura.className = "pw-field";
    input.parentNode.insertBefore(envoltura, input);
    envoltura.appendChild(input);

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "pw-toggle";
    boton.textContent = "Mostrar";
    boton.setAttribute("aria-pressed", "false");
    boton.setAttribute("aria-label", "Mostrar contraseña");
    boton.addEventListener("click", () => {
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      boton.textContent = visible ? "Mostrar" : "Ocultar";
      boton.setAttribute("aria-pressed", String(!visible));
      boton.setAttribute("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
    });
    envoltura.appendChild(boton);
  });

  /* ---- Confirmación antes de enviar formularios marcados con data-confirm ---- */
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  /* ---- Los grupos solo aplican al usuario administrativo ---- */
  const rol = document.getElementById("id_rol");
  const grupos = document.querySelector("[data-solo-staff]");
  if (rol && grupos) {
    const actualizar = () => { grupos.hidden = rol.value === "admin"; };
    rol.addEventListener("change", actualizar);
    actualizar();
  }
});
