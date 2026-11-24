import logging

from celery import shared_task
from django.core.mail import EmailMessage, get_connection

from .models import cliente, promocion, veterinaria


logger = logging.getLogger(__name__)


def _enviar_correo_promocion(promocion_obj, vet, destinatarios):
    connection = get_connection(
        host=vet.smtp_host,
        port=vet.smtp_port,
        username=vet.smtp_usuario or None,
        password=vet.smtp_password or None,
        use_tls=vet.smtp_usa_tls,
        use_ssl=vet.smtp_usa_ssl,
        fail_silently=False,
    )
    EmailMessage(
        subject=promocion_obj.titulo,
        body=promocion_obj.texto_correo,
        from_email=vet.correo,
        to=[vet.correo],
        bcc=destinatarios,
        connection=connection,
    ).send()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def enviar_promocion_task(promocion_id, veterinaria_id):
    vet = veterinaria.objects.get(pk=veterinaria_id)
    promocion_obj = promocion.objects.get(pk=promocion_id, veterinaria=vet)
    destinatarios = list(
        cliente.objects.filter(veterinaria=vet, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    if not destinatarios:
        return 0

    _enviar_correo_promocion(promocion_obj, vet, destinatarios)
    logger.info("Promoción %s enviada a %s destinatarios", promocion_obj.pk, len(destinatarios))
    return len(destinatarios)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def enviar_promocion_prueba_task(promocion_id, veterinaria_id, correo_prueba):
    vet = veterinaria.objects.get(pk=veterinaria_id)
    promocion_obj = promocion.objects.get(pk=promocion_id, veterinaria=vet)
    _enviar_correo_promocion(promocion_obj, vet, [correo_prueba])
    logger.info("Promoción de prueba %s enviada", promocion_obj.pk)
