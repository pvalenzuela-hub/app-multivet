import appclinica.fields
from django.db import migrations


def encrypt_existing_smtp_passwords(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    for vet in Veterinaria.objects.exclude(smtp_password="").iterator():
        vet.save(update_fields=["smtp_password"])


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0032_reserva_active_slot_constraint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="veterinaria",
            name="smtp_password",
            field=appclinica.fields.EncryptedCharField(blank=True, max_length=500),
        ),
        migrations.RunPython(encrypt_existing_smtp_passwords, migrations.RunPython.noop),
    ]
