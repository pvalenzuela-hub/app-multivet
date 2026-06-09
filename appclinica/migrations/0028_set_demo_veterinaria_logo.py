from django.db import migrations


DEMO_LOGO_URL = "https://ui-avatars.com/api/?name=Vetnex+Demo&background=0ea5a4&color=fff&size=512&bold=true&rounded=true&format=svg"


def set_demo_veterinaria_logo(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    Veterinaria.objects.using(schema_editor.connection.alias).filter(pk=1).update(logo=DEMO_LOGO_URL)


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0027_agendabloqueo_veterinaria_agendaevento_veterinaria_and_more"),
    ]

    operations = [
        migrations.RunPython(set_demo_veterinaria_logo, migrations.RunPython.noop),
    ]
