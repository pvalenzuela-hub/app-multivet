from django.db import migrations


DEMO_LOGO_URL = "http://127.0.0.1:8000/static/img/vetnex-logo.svg"


def update_demo_veterinaria_logo(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    Veterinaria.objects.using(schema_editor.connection.alias).filter(pk=1).update(logo=DEMO_LOGO_URL)


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0028_set_demo_veterinaria_logo"),
    ]

    operations = [
        migrations.RunPython(update_demo_veterinaria_logo, migrations.RunPython.noop),
    ]
