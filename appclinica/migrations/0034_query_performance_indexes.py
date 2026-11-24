from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0033_encrypt_smtp_password"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="atencion",
            index=models.Index(fields=["veterinaria", "fechaatencion"], name="idx_atencion_vet_fecha"),
        ),
        migrations.AddIndex(
            model_name="atenciondetalle",
            index=models.Index(fields=["created_at"], name="idx_detalle_created_at"),
        ),
        migrations.AddIndex(
            model_name="cita",
            index=models.Index(fields=["veterinaria", "estado", "fecha"], name="idx_cita_vet_estado_fecha"),
        ),
    ]
