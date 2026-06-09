from django.db import migrations


def seed_demo_data(apps, schema_editor):
    EstadoCliente = apps.get_model("appclinica", "estadocliente")
    EstadoCita = apps.get_model("appclinica", "estadocita")
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    Comuna = apps.get_model("appclinica", "comuna")
    Especie = apps.get_model("appclinica", "especie")
    Raza = apps.get_model("appclinica", "raza")
    Control = apps.get_model("appclinica", "control")
    Prestacion = apps.get_model("appclinica", "prestacion")
    Cliente = apps.get_model("appclinica", "cliente")
    Mascota = apps.get_model("appclinica", "mascota")

    estado_cliente, _ = EstadoCliente.objects.update_or_create(
        pk=1,
        defaults={"nombre": "Activo"},
    )
    EstadoCita.objects.update_or_create(
        pk=1,
        defaults={"nombre": "Pendiente"},
    )

    Veterinaria.objects.update_or_create(
        pk=1,
        defaults={
            "nombre": "Vet Demo",
            "logo": None,
            "correo": "demo@vet.local",
            "correo_prueba": "prueba@vet.local",
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_usuario": "",
            "smtp_password": "",
            "smtp_usa_tls": True,
            "smtp_usa_ssl": False,
        },
    )

    comuna_obj, _ = Comuna.objects.get_or_create(nombre="Providencia")
    especie_obj, _ = Especie.objects.get_or_create(nombre="Felino")
    raza_obj, _ = Raza.objects.get_or_create(
        especie=especie_obj,
        nombre="Angora",
    )
    Control.objects.get_or_create(nombre="Control demo")
    Prestacion.objects.get_or_create(nombre="Consulta demo")

    cliente_obj, _ = Cliente.objects.update_or_create(
        rut="22222222-2",
        defaults={
            "nombre": "Cliente Demo",
            "email": "demo@vet.local",
            "telefono": "912345678",
            "direccion": "Calle Demo 123",
            "comuna": comuna_obj,
            "origen": "sistema",
            "plansalud": "",
            "fechaplansalud": None,
            "fechaterminoplan": None,
            "estado": estado_cliente,
            "chat_id": 0,
        },
    )

    Mascota.objects.update_or_create(
        cliente=cliente_obj,
        raza=raza_obj,
        nombre="Michi Demo",
        defaults={
            "sexo": "H",
            "fechanac": None,
            "chip": None,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0022_seed_estado_basico"),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, migrations.RunPython.noop),
    ]
