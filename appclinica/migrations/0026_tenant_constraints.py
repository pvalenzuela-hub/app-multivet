from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0025_backfill_tenant_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuarioveterinaria",
            name="default_veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="usuarios_perfil",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clientes",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="rut",
            field=models.CharField(max_length=13),
        ),
        migrations.AlterField(
            model_name="especie",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="especies",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="especie",
            name="nombre",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="prestacion",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="prestaciones",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="prestacion",
            name="nombre",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="control",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="controles",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="control",
            name="nombre",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="promocion",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="promociones",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddConstraint(
            model_name="cliente",
            constraint=models.UniqueConstraint(fields=["veterinaria", "rut"], name="uq_cliente_veterinaria_rut"),
        ),
        migrations.AddConstraint(
            model_name="especie",
            constraint=models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_especie_veterinaria_nombre"),
        ),
        migrations.AddConstraint(
            model_name="prestacion",
            constraint=models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_prestacion_veterinaria_nombre"),
        ),
        migrations.AddConstraint(
            model_name="control",
            constraint=models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_control_veterinaria_nombre"),
        ),
    ]
