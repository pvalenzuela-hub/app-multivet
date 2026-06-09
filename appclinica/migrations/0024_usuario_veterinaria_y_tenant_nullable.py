from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0023_seed_demo_data"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UsuarioVeterinaria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "default_veterinaria",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="usuarios_perfil",
                        to="appclinica.veterinaria",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="veterinaria_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "usuario_veterinaria",
            },
        ),
        migrations.AddField(
            model_name="cliente",
            name="veterinaria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clientes",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="especie",
            name="veterinaria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="especies",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="prestacion",
            name="veterinaria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="prestaciones",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="control",
            name="veterinaria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="controles",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="promocion",
            name="veterinaria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="promociones",
                to="appclinica.veterinaria",
            ),
        ),
    ]
