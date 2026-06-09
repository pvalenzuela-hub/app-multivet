from django.contrib.auth import get_user_model

from .models import UsuarioVeterinaria, veterinaria

ACTIVE_VETERINARIA_SESSION_KEY = "active_veterinaria_id"


def get_master_veterinaria():
    vet = veterinaria.objects.order_by("id").first()
    if vet is None:
        vet = veterinaria.objects.create(
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
    return vet


def get_user_profile(user):
    profile, _ = UsuarioVeterinaria.objects.get_or_create(user=user)
    return profile


def get_user_default_veterinaria(user):
    profile = get_user_profile(user)
    return profile.default_veterinaria


def get_available_veterinarias(user):
    if not user.is_authenticated:
        return veterinaria.objects.none()

    if user.is_superuser:
        return veterinaria.objects.order_by("nombre", "id")

    profile = get_user_profile(user)
    if profile.default_veterinaria_id:
        return veterinaria.objects.filter(pk=profile.default_veterinaria_id)
    return veterinaria.objects.none()


def resolve_veterinaria_for_user(request, persist_default=False):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    profile = get_user_profile(user)
    vet = None

    if user.is_superuser:
        active_id = request.session.get(ACTIVE_VETERINARIA_SESSION_KEY)
        if active_id:
            vet = veterinaria.objects.filter(pk=active_id).first()
        if vet is None:
            vet = profile.default_veterinaria or get_master_veterinaria()
        if vet is not None:
            request.session[ACTIVE_VETERINARIA_SESSION_KEY] = vet.id
            if persist_default or profile.default_veterinaria_id != vet.id:
                profile.default_veterinaria = vet
                profile.save(update_fields=["default_veterinaria"])
        return vet

    vet = profile.default_veterinaria
    if vet is not None:
        request.session[ACTIVE_VETERINARIA_SESSION_KEY] = vet.id
    return vet


def set_active_veterinaria(request, vet, persist_default=True):
    request.session[ACTIVE_VETERINARIA_SESSION_KEY] = vet.id
    request.veterinaria = vet

    if getattr(request, "user", None) and request.user.is_authenticated:
        profile = get_user_profile(request.user)
        if persist_default and profile.default_veterinaria_id != vet.id:
            profile.default_veterinaria = vet
            profile.save(update_fields=["default_veterinaria"])

    return vet
