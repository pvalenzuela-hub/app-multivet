from django.db import migrations, models
import django.db.models.deletion


def backfill_agenda_tenant_data(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    Veterinaria = apps.get_model("appclinica", "veterinaria")
    AgendaEvento = apps.get_model("appclinica", "agendaevento")
    AgendaEventoHorario = apps.get_model("appclinica", "agendaeventohorario")
    Agendabloqueo = apps.get_model("appclinica", "agendabloqueo")
    Cita = apps.get_model("appclinica", "cita")
    Atencion = apps.get_model("appclinica", "atencion")
    Reserva = apps.get_model("appclinica", "reserva")

    master_vet = Veterinaria.objects.using(db_alias).order_by("id").first()
    if master_vet is None:
        master_vet = Veterinaria.objects.using(db_alias).create(
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

    for evento in AgendaEvento.objects.using(db_alias).all().iterator():
        evento.veterinaria_id = master_vet.id
        evento.save(update_fields=["veterinaria"])

    for bloqueo in Agendabloqueo.objects.using(db_alias).all().iterator():
        bloqueo.veterinaria_id = master_vet.id
        bloqueo.save(update_fields=["veterinaria"])

    for cita in Cita.objects.using(db_alias).select_related("mascota__cliente").all().iterator():
        cita.veterinaria_id = cita.mascota.cliente.veterinaria_id
        cita.save(update_fields=["veterinaria"])

    for atencion in Atencion.objects.using(db_alias).select_related("mascota__cliente").all().iterator():
        atencion.veterinaria_id = atencion.mascota.cliente.veterinaria_id
        atencion.save(update_fields=["veterinaria"])

    for horario in AgendaEventoHorario.objects.using(db_alias).select_related("evento").all().iterator():
        horario.veterinaria_id = horario.evento.veterinaria_id or master_vet.id
        horario.save(update_fields=["veterinaria"])

    for reserva in Reserva.objects.using(db_alias).select_related("evento").all().iterator():
        reserva.veterinaria_id = reserva.evento.veterinaria_id or master_vet.id
        reserva.save(update_fields=["veterinaria"])


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0026_tenant_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="agendabloqueo",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendabloqueos",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="agendaevento",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendaeventos",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="agendaevento",
            name="nombre",
            field=models.CharField(max_length=120),
        ),
        migrations.AddField(
            model_name="agendaeventohorario",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendaeventohorarios",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="atencion",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="atenciones",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="cita",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="citas",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddField(
            model_name="reserva",
            name="veterinaria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.RunPython(backfill_agenda_tenant_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="agendabloqueo",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendabloqueos",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="agendaevento",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendaeventos",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="agendaeventohorario",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agendaeventohorarios",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="atencion",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="atenciones",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="cita",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="citas",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AlterField(
            model_name="reserva",
            name="veterinaria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservas",
                to="appclinica.veterinaria",
            ),
        ),
        migrations.AddConstraint(
            model_name="agendaevento",
            constraint=models.UniqueConstraint(
                fields=["veterinaria", "nombre"],
                name="uq_agendaevento_veterinaria_nombre",
            ),
        ),
    ]
