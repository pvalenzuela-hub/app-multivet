from .tenancy import get_available_veterinarias, get_user_profile, resolve_veterinaria_for_user


def roles(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "es_administrador": False,
            "veterinaria_activa": None,
            "veterinarias_disponibles": [],
            "veterinaria_default": None,
        }

    veterinaria_activa = getattr(request, "veterinaria", None) or resolve_veterinaria_for_user(request)
    profile = get_user_profile(user)

    return {
        "es_administrador": user.groups.filter(name="Administrador").exists(),
        "es_superusuario": user.is_superuser,
        "veterinaria_activa": veterinaria_activa,
        "veterinarias_disponibles": get_available_veterinarias(user),
        "veterinaria_default": profile.default_veterinaria,
    }
