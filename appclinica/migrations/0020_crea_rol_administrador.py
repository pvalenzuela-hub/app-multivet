from django.db import migrations


def crear_rol_administrador(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    grupo, _ = Group.objects.get_or_create(name="Administrador")
    for username in ["9396495-0", "11947146-K"]:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue
        user.groups.add(grupo)


def quitar_rol_administrador(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    try:
        grupo = Group.objects.get(name="Administrador")
    except Group.DoesNotExist:
        return

    for username in ["9396495-0", "11947146-K"]:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue
        user.groups.remove(grupo)


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0019_veterinaria_smtp_host_veterinaria_smtp_password_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(crear_rol_administrador, quitar_rol_administrador),
    ]
