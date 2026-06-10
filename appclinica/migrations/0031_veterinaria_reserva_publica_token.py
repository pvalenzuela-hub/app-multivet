import uuid

from django.db import migrations, models


def populate_reserva_publica_token(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")

    for vet in Veterinaria.objects.all():
        if vet.reserva_publica_token:
            continue

        token = uuid.uuid4()
        while Veterinaria.objects.filter(reserva_publica_token=token).exists():
            token = uuid.uuid4()

        vet.reserva_publica_token = token
        vet.save(update_fields=["reserva_publica_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0030_reset_seed_sequences"),
    ]

    operations = [
        migrations.AddField(
            model_name="veterinaria",
            name="reserva_publica_token",
            field=models.UUIDField(editable=False, null=True, unique=True),
        ),
        migrations.RunPython(populate_reserva_publica_token, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="veterinaria",
            name="reserva_publica_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
