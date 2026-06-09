from django.db import migrations


def seed_estado_basico(apps, schema_editor):
    EstadoCliente = apps.get_model("appclinica", "estadocliente")
    EstadoCita = apps.get_model("appclinica", "estadocita")

    EstadoCliente.objects.update_or_create(
        pk=1,
        defaults={"nombre": "Activo"},
    )
    EstadoCita.objects.update_or_create(
        pk=1,
        defaults={"nombre": "Pendiente"},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0021_veterinaria_correo_prueba"),
    ]

    operations = [
        migrations.RunPython(seed_estado_basico, migrations.RunPython.noop),
    ]
