from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UsuarioVeterinaria
from .tenancy import get_master_veterinaria


@receiver(post_save, sender=get_user_model())
def ensure_usuario_veterinaria(sender, instance, created, **kwargs):
    if created:
        UsuarioVeterinaria.objects.get_or_create(
            user=instance,
            defaults={"default_veterinaria": get_master_veterinaria()},
        )
