from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def precio(valor):
    """
    Formato monetario es-CO: $1.234.567 (los centavos solo si existen: $8,99).
    No cambia ningún valor; solo lo presenta. Debe coincidir con fmtCents() de cart.js.
    """
    try:
        d = Decimal(valor).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    entero, decimales = f"{abs(d):.2f}".split(".")
    texto = f"{int(entero):,}".replace(",", ".")
    if decimales != "00":
        texto += f",{decimales}"
    return f"{'-' if d < 0 else ''}${texto}"
