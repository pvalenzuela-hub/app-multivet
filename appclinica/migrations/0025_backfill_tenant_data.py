from django.db import migrations


def backfill_tenant_data(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    Cliente = apps.get_model("appclinica", "cliente")
    Especie = apps.get_model("appclinica", "especie")
    Prestacion = apps.get_model("appclinica", "prestacion")
    Control = apps.get_model("appclinica", "control")
    Promocion = apps.get_model("appclinica", "promocion")
    UsuarioVeterinaria = apps.get_model("appclinica", "usuarioveterinaria")
    User = apps.get_model("auth", "User")

    master_vet = Veterinaria.objects.order_by("id").first()
    if master_vet is None:
        master_vet = Veterinaria.objects.create(
            nombre="Vet Master",
            logo=None,
            correo="master@vet.local",
            correo_prueba=None,
            smtp_host="",
            smtp_port=587,
            smtp_usuario="",
            smtp_password="",
            smtp_usa_tls=True,
            smtp_usa_ssl=False,
        )

    Cliente.objects.all().update(veterinaria=master_vet)
    Especie.objects.all().update(veterinaria=master_vet)
    Prestacion.objects.all().update(veterinaria=master_vet)
    Control.objects.all().update(veterinaria=master_vet)
    Promocion.objects.all().update(veterinaria=master_vet)

    for user in User.objects.all():
        UsuarioVeterinaria.objects.update_or_create(
            user=user,
            defaults={"default_veterinaria": master_vet},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0024_usuario_veterinaria_y_tenant_nullable"),
    ]

    operations = [
        migrations.RunPython(backfill_tenant_data, migrations.RunPython.noop),
    ]
