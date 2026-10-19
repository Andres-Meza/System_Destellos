from decimal import Decimal

from django.core.management.base import BaseCommand

from tienda.models import Producto

PACKS = [
    {
        "nombre": "Pack de decoracion #1",
        "descripcion": (
            "Incluye- Paquetes de globos (3) Incluye cinta adhesiva, Manteles para mesas "
            "y un asistente que ayuda a la gestion de el evento y la decoracion durante 2 horas maximo."
        ),
        "precio": Decimal("8.99"),
        "imagen": "pack1.png",
    },
    {
        "nombre": "Pack de decoracion #2",
        "descripcion": (
            "Decoración temática personalizada\n"
            "montaje y organización\n"
            "con hasta 2 horas de asistencia durante el evento."
        ),
        "precio": Decimal("39.99"),
        "imagen": "pack2.png",
    },
    {
        "nombre": "Pack de decoracion #3",
        "descripcion": (
            "Incluye decoración temática completa\n"
            "globos y elementos personalizados\n"
            "montaje y organización\n"
            "además de 1 persona de asistencia durante hasta 3 horas para apoyar "
            "y realizar ajustes durante el evento."
        ),
        "precio": Decimal("79.99"),
        "imagen": "pack3.jpg",
    },
]


class Command(BaseCommand):
    help = "Inserta los 3 packs de decoración originales (no duplica si ya existen)."

    def handle(self, *args, **options):
        for datos in PACKS:
            obj, creado = Producto.objects.get_or_create(nombre=datos["nombre"], defaults=datos)
            self.stdout.write(("Creado: " if creado else "Ya existía: ") + obj.nombre)
