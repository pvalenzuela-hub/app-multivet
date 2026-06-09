from .tenancy import resolve_veterinaria_for_user


class VeterinariaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.veterinaria = resolve_veterinaria_for_user(request)
        response = self.get_response(request)
        return response
