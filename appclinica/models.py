from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

# Create your models here.
class Sexo(models.TextChoices):
    MASCULINO = "M", "Macho"
    FEMENINO  = "H", "Hembra"


class DiaSemana(models.IntegerChoices):
    LUNES = 0, "Lunes"
    MARTES = 1, "Martes"
    MIERCOLES = 2, "Miercoles"
    JUEVES = 3, "Jueves"
    VIERNES = 4, "Viernes"
    SABADO = 5, "Sabado"
    DOMINGO = 6, "Domingo"


class EstadoReserva(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    CONFIRMADA = "confirmada", "Confirmada"
    CANCELADA = "cancelada", "Cancelada"


class OrigenCliente(models.TextChoices):
    SISTEMA = "sistema", "Sistema"
    WEB = "web", "Web"


VENTANA_RESERVA_DIAS = 14


def horarios_se_solapan(inicio_a, fin_a, inicio_b, fin_b):
    return inicio_a < fin_b and fin_a > inicio_b


def reservas_en_conflicto(fecha, hora_inicio, hora_fin, evento=None, veterinaria=None, exclude_pk=None):
    qs = (
        reserva.objects
        .filter(fecha=fecha, hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio)
        .exclude(estado=EstadoReserva.CANCELADA)
    )
    if veterinaria is not None:
        qs = qs.filter(veterinaria=veterinaria)
    if evento is not None:
        qs = qs.filter(evento=evento)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def slot_esta_bloqueado(fecha, hora_inicio, hora_fin, veterinaria=None):
    qs = agendabloqueo.objects.filter(activo=True, fecha_inicio__lte=fecha, fecha_fin__gte=fecha)
    if veterinaria is not None:
        qs = qs.filter(veterinaria=veterinaria)

    return (
        qs
        .filter(
            Q(hora_inicio__isnull=True, hora_fin__isnull=True) |
            Q(hora_inicio__lt=hora_fin, hora_fin__gt=hora_inicio)
        )
        .exists()
    )


def obtener_slots_disponibles(evento_obj, fecha):
    if not evento_obj or not fecha or not evento_obj.activo:
        return []

    veterinaria = getattr(evento_obj, "veterinaria", None)

    horarios = (
        agendaeventohorario.objects
        .filter(evento=evento_obj, veterinaria=veterinaria, dia_semana=fecha.weekday(), activo=True)
        .order_by("hora_inicio", "hora_fin")
    )

    disponibles = []
    for horario in horarios:
        if slot_esta_bloqueado(fecha, horario.hora_inicio, horario.hora_fin, veterinaria=veterinaria):
            continue
        if reservas_en_conflicto(fecha, horario.hora_inicio, horario.hora_fin, evento=evento_obj, veterinaria=veterinaria).exists():
            continue
        disponibles.append(horario)

    return disponibles

class comuna(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'comuna'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre}"

class estadocliente(models.Model):
    nombre = models.CharField(max_length=80)

    class Meta:
        db_table = 'estadocliente'

    def __str__(self):
        return f"{self.nombre}"

class cliente(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="clientes")
    rut = models.CharField(max_length=13, blank=False, null=False)
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=60)
    direccion = models.CharField(max_length=80)
    comuna = models.ForeignKey(comuna, on_delete=models.CASCADE)
    origen = models.CharField(max_length=20, choices=OrigenCliente.choices, default=OrigenCliente.SISTEMA)
    plansalud = models.CharField(max_length=100, blank=True, null=True)
    fechaplansalud = models.DateField(null=True, blank=True)
    fechaterminoplan = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    estado = models.ForeignKey(estadocliente, on_delete=models.CASCADE, default=1)
    chat_id = models.BigIntegerField(default=0, null=True)

    class Meta:
        db_table = 'cliente'
        constraints = [
            models.UniqueConstraint(fields=["veterinaria", "rut"], name="uq_cliente_veterinaria_rut")
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            origen_actual = cliente.objects.filter(pk=self.pk).values_list("origen", flat=True).first()
            if origen_actual == OrigenCliente.WEB:
                self.origen = OrigenCliente.WEB
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} {self.email} {self.telefono}"

class especie(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="especies")
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'especie'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_especie_veterinaria_nombre")
        ]

    def __str__(self):
        return f"{self.nombre}"


class raza(models.Model):
    nombre = models.CharField(max_length=100)
    especie = models.ForeignKey(especie, on_delete=models.CASCADE)

    class Meta:
        db_table = 'raza'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=["especie", "nombre"], name="uq_raza_especie_nombre")
        ]

    def __str__(self):
        return f"{self.nombre}"

class mascota(models.Model):
    cliente = models.ForeignKey(cliente, on_delete=models.CASCADE)
    raza = models.ForeignKey(raza, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=80, db_index=True)
    sexo = models.CharField(
        max_length=1,
        choices=Sexo.choices,
        default=Sexo.MASCULINO,
        blank=True,
        null=True,
    )
    fechanac = models.DateField(null=True)
    chip = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'mascota'

    def __str__(self):
        return f"{self.cliente} {self.raza} {self.nombre} {self.sexo}"

class atencion(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="atenciones")
    fechaatencion = models.DateTimeField(auto_now_add=True)
    mascota = models.ForeignKey(mascota, on_delete=models.CASCADE)
    evolucion = models.TextField()
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'atencion'

    def __str__(self):
        return f"{self.mascota} {self.fechaatencion}"

    def save(self, *args, **kwargs):
        if self.mascota_id and not self.veterinaria_id:
            self.veterinaria = self.mascota.cliente.veterinaria
        super().save(*args, **kwargs)

class prestacion(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="prestaciones")
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'prestacion'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_prestacion_veterinaria_nombre")
        ]

    def __str__(self):
        return f"{self.nombre}"

class estadocita(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'estadocita'

    def __str__(self):
        return f"{self.nombre}"

class control(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="controles")
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'control'
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_control_veterinaria_nombre")
        ]

    def __str__(self):
        return f"{self.nombre}"


class atenciondetalle(models.Model):
    atencion = models.ForeignKey(atencion, on_delete=models.CASCADE)
    prestacion = models.ForeignKey(prestacion, on_delete=models.CASCADE)
    observacion = models.TextField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'atenciondetalle'

    def __str__(self):
        return f"{self.atencion} {self.prestacion}"

class cita(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="citas")
    mascota = models.ForeignKey(mascota, on_delete=models.CASCADE)
    fecha = models.DateField()
    control = models.ForeignKey(control, on_delete=models.CASCADE)
    observacion = models.TextField(null=True, blank=True)
    estado = models.ForeignKey(estadocita, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cita'

    def __str__(self):
        return f"{self.mascota} {self.fecha} {self.control} {self.observacion} {self.estado}"

    def clean(self):
        errores = {}
        if self.mascota_id and self.veterinaria_id and self.mascota.cliente.veterinaria_id != self.veterinaria_id:
            errores["veterinaria"] = "La cita debe pertenecer a la veterinaria del cliente."
        if self.control_id and self.veterinaria_id and self.control.veterinaria_id != self.veterinaria_id:
            errores["control"] = "El control seleccionado no pertenece a la veterinaria."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.mascota_id and not self.veterinaria_id:
            self.veterinaria = self.mascota.cliente.veterinaria
        super().save(*args, **kwargs)


class agendaevento(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="agendaeventos")
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agendaevento"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["veterinaria", "nombre"], name="uq_agendaevento_veterinaria_nombre")
        ]

    def __str__(self):
        return self.nombre


class agendaeventohorario(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="agendaeventohorarios")
    evento = models.ForeignKey(agendaevento, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "agendaeventohorario"
        ordering = ["dia_semana", "hora_inicio", "hora_fin"]
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "dia_semana", "hora_inicio", "hora_fin"],
                name="uq_agendaevento_slot"
            )
        ]

    def clean(self):
        if self.evento_id and self.veterinaria_id and self.evento.veterinaria_id != self.veterinaria_id:
            raise ValidationError({"veterinaria": "Debe coincidir con la veterinaria del evento."})

        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError({"hora_fin": "La hora de termino debe ser mayor a la de inicio."})

        if not self.activo or self.dia_semana is None or not self.hora_inicio or not self.hora_fin or not self.evento_id:
            return

        vet = self.veterinaria or self.evento.veterinaria
        conflicto = (
            agendaeventohorario.objects
            .filter(veterinaria=vet, evento=self.evento, activo=True, dia_semana=self.dia_semana)
            .exclude(pk=self.pk)
            .filter(hora_inicio__lt=self.hora_fin, hora_fin__gt=self.hora_inicio)
            .first()
        )
        if conflicto:
            raise ValidationError(
                "Este horario se solapa con otro horario activo del mismo evento."
            )

    def save(self, *args, **kwargs):
        if self.evento_id and not self.veterinaria_id:
            self.veterinaria = self.evento.veterinaria
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.evento.nombre} - {self.get_dia_semana_display()} "
            f"{self.hora_inicio:%H:%M} a {self.hora_fin:%H:%M}"
        )


class agendabloqueo(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="agendabloqueos")
    titulo = models.CharField(max_length=120)
    motivo = models.TextField(null=True, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agendabloqueo"
        ordering = ["-fecha_inicio", "hora_inicio", "titulo"]

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError({"fecha_fin": "La fecha de termino no puede ser anterior a la de inicio."})

        if bool(self.hora_inicio) != bool(self.hora_fin):
            raise ValidationError("Debe indicar ambas horas o dejar ambas vacias para bloquear el dia completo.")

        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError({"hora_fin": "La hora de termino debe ser mayor a la de inicio."})

    def __str__(self):
        return self.titulo


class reserva(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="reservas")
    mascota = models.ForeignKey(mascota, on_delete=models.PROTECT)
    evento = models.ForeignKey(agendaevento, on_delete=models.PROTECT)
    fecha = models.DateField(db_index=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    email_contacto = models.EmailField()
    observacion = models.TextField(null=True, blank=True)
    estado = models.CharField(
        max_length=15,
        choices=EstadoReserva.choices,
        default=EstadoReserva.PENDIENTE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reserva"
        ordering = ["fecha", "hora_inicio", "mascota__nombre"]

    def clean(self):
        errores = {}

        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            errores["hora_fin"] = "La hora de termino debe ser mayor a la de inicio."

        if self.fecha and self.fecha < timezone.localdate() + timedelta(days=1):
            errores["fecha"] = "La reserva solo puede realizarse desde el dia siguiente."

        if self.evento_id and self.evento and not self.evento.activo:
            errores["evento"] = "El evento seleccionado no se encuentra disponible."

        if self.evento_id and self.veterinaria_id and self.evento.veterinaria_id != self.veterinaria_id:
            errores["veterinaria"] = "La reserva debe pertenecer a la veterinaria del evento."

        if errores:
            raise ValidationError(errores)

        if not all([self.evento_id, self.fecha, self.hora_inicio, self.hora_fin]):
            return

        horario_valido = agendaeventohorario.objects.filter(
            veterinaria=self.veterinaria,
            evento=self.evento,
            dia_semana=self.fecha.weekday(),
            hora_inicio=self.hora_inicio,
            hora_fin=self.hora_fin,
            activo=True,
        ).exists()
        if not horario_valido:
            raise ValidationError("La fecha y el horario no corresponden a un slot disponible para este evento.")

        if slot_esta_bloqueado(self.fecha, self.hora_inicio, self.hora_fin, veterinaria=self.veterinaria):
            raise ValidationError("El horario seleccionado se encuentra bloqueado.")

        if reservas_en_conflicto(self.fecha, self.hora_inicio, self.hora_fin, evento=self.evento, veterinaria=self.veterinaria, exclude_pk=self.pk).exists():
            raise ValidationError("El horario seleccionado ya fue reservado.")

    def save(self, *args, **kwargs):
        if self.evento_id and not self.veterinaria_id:
            self.veterinaria = self.evento.veterinaria
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.fecha} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M} "
            f"{self.mascota.nombre} / {self.evento.nombre}"
        )


class veterinaria(models.Model):
    nombre = models.CharField(max_length=150)
    logo = models.URLField(null=True, blank=True)
    correo = models.EmailField()
    correo_prueba = models.EmailField(null=True, blank=True)
    smtp_host = models.CharField(max_length=150, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_usuario = models.CharField(max_length=150, blank=True)
    smtp_password = models.CharField(max_length=150, blank=True)
    smtp_usa_tls = models.BooleanField(default=True)
    smtp_usa_ssl = models.BooleanField(default=False)

    class Meta:
        db_table = "veterinaria"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class UsuarioVeterinaria(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="veterinaria_profile")
    default_veterinaria = models.ForeignKey(
        veterinaria,
        on_delete=models.PROTECT,
        related_name="usuarios_perfil",
    )

    class Meta:
        db_table = "usuario_veterinaria"

    def __str__(self):
        return f"{self.user} -> {self.default_veterinaria or 'sin veterinaria'}"


class promocion(models.Model):
    veterinaria = models.ForeignKey("veterinaria", on_delete=models.PROTECT, related_name="promociones")
    titulo = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    texto_correo = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promocion"
        ordering = ["-fecha_creacion", "titulo"]

    def __str__(self):
        return self.titulo
