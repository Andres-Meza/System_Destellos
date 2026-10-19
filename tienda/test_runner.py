"""
Los modelos originales son managed=False (tablas ya existentes en MySQL), por lo que
Django no las crea en la base de datos de PRUEBA. Este runner las crea una sola vez
al preparar la base de datos de pruebas.
Se activa con TEST_RUNNER en settings.py.
"""
from django.db import connections
from django.test.runner import DiscoverRunner


def crear_tablas_existentes(connection):
    from tienda.models import Cliente, DetallePedido, Pago, Pedido, Producto

    existentes = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for modelo in (Cliente, Producto, Pedido, DetallePedido, Pago):  # orden por dependencias
            if modelo._meta.db_table not in existentes:
                editor.create_model(modelo)


class RunnerTablasExistentes(DiscoverRunner):
    def setup_databases(self, **kwargs):
        config = super().setup_databases(**kwargs)
        for alias in connections:
            crear_tablas_existentes(connections[alias])
        return config
