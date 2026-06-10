import os

from django.core.management.color import no_style
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from appclinica.models import (
    cliente,
    control,
    estadocita,
    estadocliente,
    prestacion,
    veterinaria,
)


DEFAULT_LOGO_URL = (
    "https://ui-avatars.com/api/?name=Vetnex&background=0ea5a4&color=fff"
    "&size=512&bold=true&rounded=true&format=svg"
)
DEMO_CLIENT_RUT = "22222222-2"
DEMO_CONTROL_NAME = "Control demo"
DEMO_PRESTACION_NAME = "Consulta demo"


def _clean(value):
    return (value or "").strip()


def _unsafe_logo(url):
    lowered = url.lower()
    return any(token in lowered for token in ("127.0.0.1", "localhost", "logopetsalud"))


def _resolve_logo_url(explicit_logo, existing_logo):
    explicit_logo = _clean(explicit_logo)
    if explicit_logo:
        return explicit_logo

    public_base = _clean(os.getenv("PUBLIC_SITE_URL") or os.getenv("SITE_URL"))
    if public_base:
        return f"{public_base.rstrip('/')}/static/img/vetnex-logo.svg"

    if existing_logo and not _unsafe_logo(existing_logo):
        return existing_logo

    return DEFAULT_LOGO_URL


def _reset_sequences(models):
    sql_statements = connection.ops.sequence_reset_sql(no_style(), models)
    with connection.cursor() as cursor:
        for statement in sql_statements:
            cursor.execute(statement)


class Command(BaseCommand):
    help = "Seed idempotente para una base de produccion Vetnex."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", default=os.getenv("SEED_VETERINARIA_NOMBRE", "Vetnex"))
        parser.add_argument("--correo", default=os.getenv("SEED_VETERINARIA_CORREO", "contacto@vetnex.cl"))
        parser.add_argument("--correo-prueba", default=os.getenv("SEED_VETERINARIA_CORREO_PRUEBA", ""))
        parser.add_argument("--logo-url", default=os.getenv("SEED_VETERINARIA_LOGO_URL", ""))
        parser.add_argument("--smtp-host", default=os.getenv("SEED_VETERINARIA_SMTP_HOST", ""))
        parser.add_argument("--smtp-port", type=int, default=int(os.getenv("SEED_VETERINARIA_SMTP_PORT", "587")))
        parser.add_argument("--smtp-usuario", default=os.getenv("SEED_VETERINARIA_SMTP_USUARIO", ""))
        parser.add_argument("--smtp-password", default=os.getenv("SEED_VETERINARIA_SMTP_PASSWORD", ""))

    def handle(self, *args, **options):
        with transaction.atomic():
            estadocliente.objects.update_or_create(
                pk=1,
                defaults={"nombre": "Activo"},
            )
            estadocita.objects.update_or_create(
                pk=1,
                defaults={"nombre": "Pendiente"},
            )

            existing_vet = veterinaria.objects.filter(pk=1).first()
            logo_url = _resolve_logo_url(options["logo_url"], getattr(existing_vet, "logo", None))

            vet = veterinaria.objects.update_or_create(
                pk=1,
                defaults={
                    "nombre": _clean(options["nombre"]) or (existing_vet.nombre if existing_vet else "Vetnex"),
                    "logo": logo_url,
                    "correo": _clean(options["correo"]) or (existing_vet.correo if existing_vet else "contacto@vetnex.cl"),
                    "correo_prueba": _clean(options["correo_prueba"]) if _clean(options["correo_prueba"]) else (existing_vet.correo_prueba if existing_vet else None),
                    "smtp_host": _clean(options["smtp_host"]) or (existing_vet.smtp_host if existing_vet else ""),
                    "smtp_port": options["smtp_port"] or (existing_vet.smtp_port if existing_vet else 587),
                    "smtp_usuario": _clean(options["smtp_usuario"]) or (existing_vet.smtp_usuario if existing_vet else ""),
                    "smtp_password": _clean(options["smtp_password"]) or (existing_vet.smtp_password if existing_vet else ""),
                    "smtp_usa_tls": True if existing_vet is None else existing_vet.smtp_usa_tls,
                    "smtp_usa_ssl": False if existing_vet is None else existing_vet.smtp_usa_ssl,
                },
            )[0]

            cliente.objects.filter(rut=DEMO_CLIENT_RUT).delete()
            control.objects.filter(veterinaria=vet, nombre=DEMO_CONTROL_NAME).update(nombre="Control general")
            prestacion.objects.filter(veterinaria=vet, nombre=DEMO_PRESTACION_NAME).update(nombre="Consulta general")
            control.objects.update_or_create(veterinaria=vet, nombre="Control general", defaults={})
            prestacion.objects.update_or_create(veterinaria=vet, nombre="Consulta general", defaults={})

            _reset_sequences([veterinaria, estadocliente, estadocita])

        self.stdout.write(self.style.SUCCESS("Seed de produccion aplicado correctamente."))
