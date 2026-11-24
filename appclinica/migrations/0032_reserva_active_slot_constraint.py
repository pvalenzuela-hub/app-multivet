from django.db import migrations, models
from django.db.models import Count, Q


def ensure_no_duplicate_active_slots(apps, schema_editor):
    Reserva = apps.get_model("appclinica", "reserva")
    duplicates = (
        Reserva.objects.exclude(estado="cancelada")
        .values("veterinaria_id", "evento_id", "fecha", "hora_inicio", "hora_fin")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    if duplicates.exists():
        raise RuntimeError(
            "Existen reservas activas duplicadas. Resuélvalas antes de aplicar la restricción uq_reserva_slot_activo."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0031_veterinaria_reserva_publica_token"),
    ]

    operations = [
        migrations.RunPython(ensure_no_duplicate_active_slots, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="reserva",
            constraint=models.UniqueConstraint(
                fields=("veterinaria", "evento", "fecha", "hora_inicio", "hora_fin"),
                condition=~Q(estado="cancelada"),
                name="uq_reserva_slot_activo",
            ),
        ),
    ]
