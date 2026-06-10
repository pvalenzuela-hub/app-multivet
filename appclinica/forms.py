# appclinica/forms.py
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, formset_factory
from django.db.models.functions import Lower
from .models import (
    cliente, mascota, atencion, atenciondetalle, cita, especie, raza, control, prestacion,
    estadocliente, estadocita,
    agendaevento, agendaeventohorario, agendabloqueo, reserva, comuna, Sexo,
    promocion, veterinaria,
    VENTANA_RESERVA_DIAS,
)
from .utils.rut import rut_validate_and_format
from django.utils import timezone


# -------------------------
# Bootstrap helper
# -------------------------
def apply_bootstrap(form: forms.BaseForm) -> None:
    """
    Aplica clases Bootstrap 5 a los widgets para un look consistente.
    """
    for name, field in form.fields.items():
        widget = field.widget
        current = widget.attrs.get("class", "")

        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs["class"] = (current + " form-select").strip()
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = (current + " form-check-input").strip()
        else:
            widget.attrs["class"] = (current + " form-control").strip()

        widget.attrs.setdefault("autocomplete", "off")


class EventoSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            descripcion = ""
            instance = getattr(value, "instance", None)
            if instance is None and hasattr(value, "value"):
                try:
                    instance = self.choices.queryset.get(pk=value.value)
                except agendaevento.DoesNotExist:
                    instance = None
            if instance is not None:
                descripcion = instance.descripcion or ""
            option["attrs"]["data-descripcion"] = descripcion
        return option


# -------------------------
# Cliente
# -------------------------
class ClienteForm(forms.ModelForm):
    class Meta:
        model = cliente
        fields = [
            "rut", "nombre", "email", "telefono", "direccion", "origen",
            "comuna", "plansalud", "fechaplansalud", "fechaterminoplan",
        ]
        widgets = {
            "fechaplansalud": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "fechaterminoplan": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)

        if self.instance and self.instance.pk:
            self.fields["origen"].disabled = True
        else:
            self.fields["origen"].initial = "sistema"
            self.fields["origen"].widget = forms.HiddenInput()

        # Clave para que el <input type="date"> se pinte en edición y acepte el formato ISO
        for f in ("fechaplansalud", "fechaterminoplan"):
            if f in self.fields:
                self.fields[f].input_formats = ["%Y-%m-%d"]

    def clean_rut(self):
        raw = self.cleaned_data.get("rut", "")
        try:
            formatted = rut_validate_and_format(raw)  # Debe retornar canónico: 99999999-X
        except ValueError as e:
            raise ValidationError(str(e))
        return formatted

# -------------------------
# Mascota (cliente viene por URL / vista)
# -------------------------
class MascotaForm(forms.ModelForm):
    class Meta:
        model = mascota
        fields = ["raza", "nombre", "sexo", "fechanac", "chip"]
        widgets = {
            "raza": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de la mascota"}),
            "sexo": forms.Select(attrs={"class": "form-select"}),
            "fechanac": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "chip": forms.NumberInput(attrs={"class": "form-control", "placeholder": "N° de chip"}),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["chip"].required = False  # asegura que no se exija

        qs = raza.objects.select_related("especie")
        if veterinaria is not None:
            qs = qs.filter(especie__veterinaria=veterinaria)
        self.fields["raza"].queryset = qs.order_by(Lower("nombre"))
        apply_bootstrap(self)



# -------------------------
# Atención (cabecera)
# -------------------------
class AtencionForm(forms.ModelForm):
    class Meta:
        model = atencion
        fields = ["mascota", "evolucion"]
        widgets = {
            "mascota": forms.Select(attrs={"class": "form-select"}),
            "evolucion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        cliente_obj = kwargs.pop("cliente", None)  # permite filtrar mascotas por cliente
        veterinaria = kwargs.pop("veterinaria", None)
        super().__init__(*args, **kwargs)

        apply_bootstrap(self)

        if cliente_obj is not None:
            self.fields["mascota"].queryset = (
                mascota.objects.filter(cliente=cliente_obj).order_by("nombre")
            )
        elif veterinaria is not None:
            self.fields["mascota"].queryset = (
                mascota.objects.filter(cliente__veterinaria=veterinaria).order_by("nombre")
            )
        if veterinaria is not None:
            self.instance.veterinaria = veterinaria

        # Mostrar solo el nombre en el select (no el __str__)
        self.fields["mascota"].label_from_instance = lambda obj: obj.nombre


# -------------------------
# Detalle Atención (prestaciones)
# -------------------------
class AtencionDetalleForm(forms.ModelForm):
    class Meta:
        model = atenciondetalle
        fields = ["prestacion", "observacion"]
        widgets = {
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.fields["prestacion"].queryset = prestacion.objects.filter(veterinaria=veterinaria).order_by("nombre")
        apply_bootstrap(self)


AtencionDetalleFormSet = inlineformset_factory(
    parent_model=atencion,
    model=atenciondetalle,
    form=AtencionDetalleForm,
    extra=1,
    can_delete=True
)


# -------------------------
# Citas (sin estado en el form: se fuerza en la vista estado_id=1)
# -------------------------
class CitaForm(forms.ModelForm):
    class Meta:
        model = cita
        # mascota y estado se asignan en la vista
        fields = ["fecha", "control", "observacion"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.fields["control"].queryset = control.objects.filter(veterinaria=veterinaria).order_by("nombre")
            self.instance.veterinaria = veterinaria
        apply_bootstrap(self)

        self.fields["fecha"].input_formats = ["%Y-%m-%d"]


class CitaUpdateForm(forms.ModelForm):
    class Meta:
        model = cita
        fields = ["fecha", "control", "observacion", "estado"]
        widgets = {
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "control": forms.Select(attrs={"class": "form-select"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "estado": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.fields["control"].queryset = control.objects.filter(veterinaria=veterinaria).order_by("nombre")
            self.instance.veterinaria = veterinaria
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]

        # opcional: fuerza el mínimo en el HTML (ayuda UX, no reemplaza validación server)
        self.fields["fecha"].widget.attrs["min"] = timezone.localdate().strftime("%Y-%m-%d")

    def clean_fecha(self):
        f = self.cleaned_data.get("fecha")
        if not f:
            return f

        hoy = timezone.localdate()
        if f < hoy:
            raise forms.ValidationError("La fecha de la cita no puede ser anterior a hoy.")
        return f

CitaFormSet = formset_factory(
    CitaForm,
    extra=1,
    can_delete=True
)

class CitaEstadoForm(forms.ModelForm):
    """
    Form mínimo: solo permite cambiar el estado.
    """
    class Meta:
        model = cita
        fields = ["estado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)

class EspecieForm(forms.ModelForm):
    class Meta:
        model = especie
        fields = ["nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class RazaForm(forms.ModelForm):
    class Meta:
        model = raza
        fields = ["especie", "nombre"]

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.fields["especie"].queryset = especie.objects.filter(veterinaria=veterinaria).order_by("nombre")
        apply_bootstrap(self)


class PrestacionForm(forms.ModelForm):
    class Meta:
        model = prestacion
        fields = ["nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class ControlForm(forms.ModelForm):
    class Meta:
        model = control
        fields = ["nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class EstadoClienteForm(forms.ModelForm):
    class Meta:
        model = estadocliente
        fields = ["nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class EstadoCitaForm(forms.ModelForm):
    class Meta:
        model = estadocita
        fields = ["nombre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)

class AtencionUpdateForm(forms.ModelForm):
    class Meta:
        model = atencion
        fields = ["evolucion"]
        widgets = {
            "evolucion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "Ingrese observaciones clínicas",
            })
        }

class AtencionDetalleForm(forms.ModelForm):
    class Meta:
        model = atenciondetalle
        fields = ["prestacion", "observacion"]
        widgets = {
            "prestacion": forms.Select(attrs={"class": "form-select"}),
            "observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Observación (opcional)"
            }),
        }


class AgendaEventoForm(forms.ModelForm):
    class Meta:
        model = agendaevento
        fields = ["nombre", "descripcion", "activo"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.instance.veterinaria = veterinaria
        apply_bootstrap(self)


class AgendaEventoHorarioForm(forms.ModelForm):
    def __init__(self, *args, evento=None, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if evento is not None:
            self.instance.evento = evento
            self.instance.veterinaria = getattr(evento, "veterinaria", None)
        elif veterinaria is not None:
            self.instance.veterinaria = veterinaria
        apply_bootstrap(self)
        self.fields["hora_inicio"].input_formats = ["%H:%M"]
        self.fields["hora_fin"].input_formats = ["%H:%M"]

    class Meta:
        model = agendaeventohorario
        fields = ["dia_semana", "hora_inicio", "hora_fin", "activo"]
        widgets = {
            "dia_semana": forms.Select(attrs={"class": "form-select"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }


class AgendaBloqueoForm(forms.ModelForm):
    class Meta:
        model = agendabloqueo
        fields = ["titulo", "motivo", "fecha_inicio", "fecha_fin", "hora_inicio", "hora_fin", "activo"]
        widgets = {
            "motivo": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        if veterinaria is not None:
            self.instance.veterinaria = veterinaria
        apply_bootstrap(self)
        self.fields["fecha_inicio"].input_formats = ["%Y-%m-%d"]
        self.fields["fecha_fin"].input_formats = ["%Y-%m-%d"]
        self.fields["hora_inicio"].input_formats = ["%H:%M"]
        self.fields["hora_fin"].input_formats = ["%H:%M"]


class ReservaAccesoForm(forms.Form):
    rut = forms.CharField(label="RUT", max_length=13)
    email = forms.EmailField(label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
        self.fields["rut"].widget.attrs.update({
            "placeholder": "12345678-9",
            "pattern": r"\d{7,8}-[0-9Kk]",
        })

    def clean_rut(self):
        try:
            return rut_validate_and_format(self.cleaned_data.get("rut", ""))
        except ValueError as e:
            raise ValidationError(str(e))

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()


class ReservaPublicaBusquedaForm(forms.Form):
    mascota = forms.ModelChoiceField(queryset=mascota.objects.none(), label="Mascota")
    evento = forms.ModelChoiceField(queryset=agendaevento.objects.none(), label="Evento", widget=EventoSelect)
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    email_contacto = forms.EmailField(label="Email de contacto")
    observacion = forms.CharField(
        label="Observación",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, veterinaria=None, **kwargs):
        cliente_obj = kwargs.pop("cliente_obj")
        super().__init__(*args, **kwargs)
        self.cliente_obj = cliente_obj
        self.veterinaria = veterinaria

        self.fields["mascota"].queryset = mascota.objects.filter(
            cliente=cliente_obj,
            cliente__veterinaria=veterinaria,
        ).order_by("nombre")
        self.fields["mascota"].label_from_instance = lambda obj: obj.nombre
        self.fields["evento"].queryset = agendaevento.objects.filter(veterinaria=veterinaria, activo=True).order_by("nombre")
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]

        manana = timezone.localdate() + timedelta(days=1)
        max_fecha = manana + timedelta(days=VENTANA_RESERVA_DIAS - 1)
        self.fields["fecha"].widget.attrs["min"] = manana.strftime("%Y-%m-%d")
        self.fields["fecha"].widget.attrs["max"] = max_fecha.strftime("%Y-%m-%d")
        self.initial.setdefault("email_contacto", cliente_obj.email)
        apply_bootstrap(self)

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if not fecha:
            return fecha

        manana = timezone.localdate() + timedelta(days=1)
        max_fecha = manana + timedelta(days=VENTANA_RESERVA_DIAS - 1)
        if fecha < manana:
            raise forms.ValidationError("La reserva solo puede realizarse desde el dia siguiente.")
        if fecha > max_fecha:
            raise forms.ValidationError(f"Solo se permite reservar dentro de los proximos {VENTANA_RESERVA_DIAS} dias.")
        return fecha

    def clean_email_contacto(self):
        return (self.cleaned_data.get("email_contacto") or "").strip().lower()


class ReservaPublicaRegistroForm(forms.Form):
    nombre = forms.CharField(label="Nombre", max_length=100)
    telefono = forms.CharField(label="Telefono", max_length=60)
    direccion = forms.CharField(label="Direccion", max_length=80)
    comuna = forms.ModelChoiceField(queryset=comuna.objects.none(), label="Comuna")
    raza = forms.ModelChoiceField(queryset=raza.objects.none(), label="Raza")
    nombre_mascota = forms.CharField(label="Nombre mascota", max_length=80)
    sexo = forms.ChoiceField(label="Sexo", choices=Sexo.choices)
    fechanac = forms.DateField(
        label="Fecha nacimiento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    origen = forms.CharField(initial="web", required=False, widget=forms.HiddenInput())

    def __init__(self, *args, veterinaria=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.veterinaria = veterinaria
        self.fields["comuna"].queryset = comuna.objects.order_by("nombre")
        qs = raza.objects.select_related("especie")
        if veterinaria is not None:
            qs = qs.filter(especie__veterinaria=veterinaria)
        self.fields["raza"].queryset = qs.order_by(Lower("nombre"))
        self.fields["fechanac"].input_formats = ["%Y-%m-%d"]
        apply_bootstrap(self)

    def clean_origen(self):
        return "web"


class ReservaSlotForm(forms.Form):
    horario_id = forms.TypedChoiceField(
        label="Horarios disponibles",
        coerce=int,
        empty_value="",
        choices=(),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        slots = kwargs.pop("slots", [])
        super().__init__(*args, **kwargs)
        self.fields["horario_id"].choices = [
            (slot.id, f"{slot.hora_inicio:%H:%M} a {slot.hora_fin:%H:%M}")
            for slot in slots
        ]


class ReservaEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=reserva._meta.get_field("estado").choices)
    observacion = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)

        if self.instance is not None and self.instance.pk:
            self.initial.setdefault("estado", self.instance.estado)
            self.initial.setdefault("observacion", self.instance.observacion)

    def save(self):
        if self.instance is None:
            raise ValueError("ReservaEstadoForm requiere una instancia")

        self.instance.estado = self.cleaned_data["estado"]
        self.instance.observacion = self.cleaned_data.get("observacion")
        self.instance.save(update_fields=["estado", "observacion", "updated_at"])
        return self.instance


class PromocionForm(forms.ModelForm):
    class Meta:
        model = promocion
        fields = ["titulo", "descripcion", "texto_correo"]
        labels = {
            "titulo": "Nombre o titulo",
            "texto_correo": "Texto del correo",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 2}),
            "texto_correo": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class VeterinariaForm(forms.ModelForm):
    class Meta:
        model = veterinaria
        fields = [
            "nombre", "logo", "correo", "correo_prueba", "smtp_host", "smtp_port",
            "smtp_usuario", "smtp_password", "smtp_usa_tls", "smtp_usa_ssl",
        ]
        labels = {
            "logo": "URL del logo",
            "correo": "Correo remitente",
            "correo_prueba": "Correo de prueba",
            "smtp_host": "Servidor SMTP",
            "smtp_port": "Puerto SMTP",
            "smtp_usuario": "Usuario SMTP",
            "smtp_password": "Password SMTP",
            "smtp_usa_tls": "Usa TLS",
            "smtp_usa_ssl": "Usa SSL",
        }
        widgets = {
            "smtp_password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
