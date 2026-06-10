from django.core.management.color import no_style
from django.db import migrations


def reset_seed_sequences(apps, schema_editor):
    Veterinaria = apps.get_model("appclinica", "veterinaria")
    EstadoCliente = apps.get_model("appclinica", "estadocliente")
    EstadoCita = apps.get_model("appclinica", "estadocita")

    sql_statements = schema_editor.connection.ops.sequence_reset_sql(
        no_style(),
        [Veterinaria, EstadoCliente, EstadoCita],
    )
    with schema_editor.connection.cursor() as cursor:
        for statement in sql_statements:
            cursor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [
        ("appclinica", "0029_update_demo_veterinaria_logo_to_vetnex"),
    ]

    operations = [
        migrations.RunPython(reset_seed_sequences, migrations.RunPython.noop),
    ]
