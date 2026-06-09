from django.contrib import admin

from .models import (
    UsuarioVeterinaria,
    agendabloqueo,
    agendaevento,
    agendaeventohorario,
    atencion,
    atenciondetalle,
    cita,
    cliente,
    comuna,
    control,
    estadocita,
    estadocliente,
    mascota,
    promocion,
    prestacion,
    raza,
    reserva,
    especie,
    veterinaria,
)


class TenantScopedAdmin(admin.ModelAdmin):
    tenant_filter = "veterinaria"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        vet = getattr(request, "veterinaria", None)
        if vet is None or not self.tenant_filter:
            return qs.none()
        return qs.filter(**{self.tenant_filter: vet})

    def save_model(self, request, obj, form, change):
        vet = getattr(request, "veterinaria", None)
        if vet is not None and hasattr(obj, "veterinaria") and not getattr(obj, "veterinaria_id", None):
            obj.veterinaria = vet
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "veterinaria" and not request.user.is_superuser:
            vet = getattr(request, "veterinaria", None)
            kwargs["queryset"] = veterinaria.objects.filter(pk=getattr(vet, "pk", None))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RazaAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("especie")
        vet = getattr(request, "veterinaria", None)
        if vet is None:
            return qs.none()
        return qs.select_related("especie").filter(especie__veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "especie" and not request.user.is_superuser:
            vet = getattr(request, "veterinaria", None)
            kwargs["queryset"] = especie.objects.filter(veterinaria=vet).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AgendaEventoHorarioAdmin(TenantScopedAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if db_field.name == "evento" and vet is not None and not request.user.is_superuser:
            kwargs["queryset"] = agendaevento.objects.filter(veterinaria=vet).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AgendabloqueoAdmin(TenantScopedAdmin):
    pass


class ReservaAdmin(TenantScopedAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if vet is not None and not request.user.is_superuser:
            if db_field.name == "mascota":
                kwargs["queryset"] = mascota.objects.filter(cliente__veterinaria=vet).order_by("nombre")
            if db_field.name == "evento":
                kwargs["queryset"] = agendaevento.objects.filter(veterinaria=vet, activo=True).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MascotaAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("cliente", "raza")
        vet = getattr(request, "veterinaria", None)
        if vet is None:
            return qs.none()
        return qs.select_related("cliente", "raza").filter(cliente__veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if db_field.name == "cliente" and vet is not None and not request.user.is_superuser:
            kwargs["queryset"] = cliente.objects.filter(veterinaria=vet).order_by("nombre")
        if db_field.name == "raza" and vet is not None and not request.user.is_superuser:
            kwargs["queryset"] = raza.objects.select_related("especie").filter(especie__veterinaria=vet).order_by("especie__nombre", "nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AtencionAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("mascota", "mascota__cliente")
        vet = getattr(request, "veterinaria", None)
        if vet is None:
            return qs.none()
        return qs.select_related("mascota", "mascota__cliente").filter(veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if db_field.name == "mascota" and vet is not None and not request.user.is_superuser:
            kwargs["queryset"] = mascota.objects.filter(cliente__veterinaria=vet).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AtencionDetalleAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("atencion", "prestacion")
        vet = getattr(request, "veterinaria", None)
        if vet is None:
            return qs.none()
        return qs.select_related("atencion", "prestacion").filter(atencion__mascota__cliente__veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if vet is not None and not request.user.is_superuser:
            if db_field.name == "atencion":
                kwargs["queryset"] = atencion.objects.filter(veterinaria=vet).order_by("-fechaatencion")
            if db_field.name == "prestacion":
                kwargs["queryset"] = prestacion.objects.filter(veterinaria=vet).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CitaAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs.select_related("mascota", "mascota__cliente", "control", "estado")
        vet = getattr(request, "veterinaria", None)
        if vet is None:
            return qs.none()
        return qs.select_related("mascota", "mascota__cliente", "control", "estado").filter(veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        vet = getattr(request, "veterinaria", None)
        if vet is not None and not request.user.is_superuser:
            if db_field.name == "mascota":
                kwargs["queryset"] = mascota.objects.filter(cliente__veterinaria=vet).order_by("nombre")
            if db_field.name == "control":
                kwargs["queryset"] = control.objects.filter(veterinaria=vet).order_by("nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AgendaEventoAdmin(TenantScopedAdmin):
    pass


admin.site.register(comuna)
admin.site.register(especie, TenantScopedAdmin)
admin.site.register(raza, RazaAdmin)
admin.site.register(estadocita)
admin.site.register(estadocliente)
admin.site.register(cliente, TenantScopedAdmin)
admin.site.register(prestacion, TenantScopedAdmin)
admin.site.register(control, TenantScopedAdmin)
admin.site.register(atencion, AtencionAdmin)
admin.site.register(atenciondetalle, AtencionDetalleAdmin)
admin.site.register(cita, CitaAdmin)
admin.site.register(mascota, MascotaAdmin)
admin.site.register(agendaevento, AgendaEventoAdmin)
admin.site.register(agendaeventohorario, AgendaEventoHorarioAdmin)
admin.site.register(agendabloqueo, AgendabloqueoAdmin)
admin.site.register(reserva, ReservaAdmin)
admin.site.register(veterinaria)
admin.site.register(UsuarioVeterinaria)
admin.site.register(promocion, TenantScopedAdmin)
