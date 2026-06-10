from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import EmailMessage, get_connection
from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch, Count, Case, When, Value, IntegerField
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    ClienteForm, MascotaForm, AtencionForm,
    AtencionDetalleFormSet, CitaFormSet,
    MascotaForm, CitaForm, CitaEstadoForm,
    EspecieForm, RazaForm, PrestacionForm, ControlForm,
    EstadoClienteForm, EstadoCitaForm,
    AtencionUpdateForm, AtencionDetalleForm,
    CitaUpdateForm, AgendaEventoForm, AgendaEventoHorarioForm,
    AgendaBloqueoForm, ReservaAccesoForm, ReservaPublicaBusquedaForm,
    ReservaSlotForm, ReservaEstadoForm, ReservaPublicaRegistroForm,
    PromocionForm, VeterinariaForm,
)

from .models import (
    cliente, mascota, atencion, atenciondetalle, cita, especie, control, raza, prestacion, comuna,
    estadocliente, estadocita,
    agendaevento, agendaeventohorario, agendabloqueo, reserva, promocion, veterinaria,
    VENTANA_RESERVA_DIAS, obtener_slots_disponibles, OrigenCliente,
)
from .tenancy import (
    ACTIVE_VETERINARIA_SESSION_KEY,
    get_master_veterinaria,
    resolve_veterinaria_for_user,
    set_active_veterinaria,
)
from .utils.rut import rut_validate_and_format
import re
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.postgres.aggregates import StringAgg


ESTADO_CITA_DEFAULT_ID = 1  # <<-- el estado por defecto requerido
RESERVA_CLIENTE_SESSION_KEY = "reserva_publica_cliente_id"
RESERVA_DRAFT_SESSION_KEY = "reserva_publica_draft"
RESERVA_REGISTRO_SESSION_KEY = "reserva_publica_registro"


def current_veterinaria(request):
    vet = getattr(request, "veterinaria", None)
    if vet is None:
        raise PermissionDenied("No hay una veterinaria activa para este usuario.")
    return vet


def usuario_es_administrador(user):
    return user.is_authenticated and user.groups.filter(name="Administrador").exists()


def usuario_es_superusuario(user):
    return user.is_authenticated and user.is_superuser


def administrador_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not usuario_es_administrador(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def superusuario_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_reserva_cliente_publico(request):
    master_vet = get_master_veterinaria()
    cliente_id = request.session.get(RESERVA_CLIENTE_SESSION_KEY)
    if not cliente_id:
        return None
    return cliente.objects.filter(pk=cliente_id, veterinaria=master_vet).first()


def _clear_reserva_publica_session(request, clear_cliente=False):
    request.session.pop(RESERVA_DRAFT_SESSION_KEY, None)
    request.session.pop(RESERVA_REGISTRO_SESSION_KEY, None)
    if clear_cliente:
        request.session.pop(RESERVA_CLIENTE_SESSION_KEY, None)


def _get_reserva_publica_draft(request, cliente_obj):
    master_vet = get_master_veterinaria()
    draft = request.session.get(RESERVA_DRAFT_SESSION_KEY)
    if not draft:
        return None

    try:
        fecha = date.fromisoformat(draft["fecha"])
        pet = mascota.objects.get(pk=draft["mascota_id"], cliente=cliente_obj, cliente__veterinaria=master_vet)
        evento_obj = agendaevento.objects.get(pk=draft["evento_id"], activo=True, veterinaria=master_vet)
    except (KeyError, TypeError, ValueError, mascota.DoesNotExist, agendaevento.DoesNotExist):
        request.session.pop(RESERVA_DRAFT_SESSION_KEY, None)
        return None

    return {
        "mascota": pet,
        "evento": evento_obj,
        "fecha": fecha,
        "email_contacto": draft.get("email_contacto", cliente_obj.email),
        "observacion": draft.get("observacion", ""),
    }


def _add_validation_error_to_form(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            target = field if field in form.fields else None
            for error in errors:
                form.add_error(target, error)
        return

    for error in exc.messages:
        form.add_error(None, error)
@login_required
def cita_create_cliente(request, cliente_id):
    """
    Crea una cita asociada a una mascota del cliente.
    Estado NO se muestra: se fuerza a estado_id = 1.
    """
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    mascotas_cliente = (
        mascota.objects
        .filter(cliente=c)
        .order_by("nombre")
    )

    if request.method == "POST":
        form = CitaForm(request.POST, veterinaria=vet)

        # mascota viene por POST (select manual en el template)
        mascota_id = request.POST.get("mascota_id")
        pet = mascotas_cliente.filter(id=mascota_id).first()

        if not pet:
            form.add_error(None, "Debe seleccionar una mascota válida para este cliente.")


        if form.is_valid() and pet:
            cit = form.save(commit=False)
            cit.mascota = pet
            cit.veterinaria = vet
            cit.estado_id = ESTADO_CITA_DEFAULT_ID
            # Validación server-side fecha >= hoy (opcional pero recomendado)
            if cit.fecha and cit.fecha < timezone.localdate():
                form.add_error("fecha", "La fecha de la cita no puede ser anterior a hoy.")
            else:
                cit.save()
                messages.success(request, "Cita creada correctamente.")
                return redirect("citas_por_cliente", cliente_id=c.id)

    else:
        form = CitaForm(veterinaria=vet)

    return render(request, "cita/cita_form.html", {
        "cliente": c,
        "form": form,
        "mascotas": mascotas_cliente,
    })

def rut_compact(r: str) -> str:
    """Quita puntos/espacios y deja guion si viene."""
    r = (r or "").strip().upper()
    r = re.sub(r"[^0-9K\-]", "", r)      # deja solo 0-9, K y '-'
    r = r.replace("--", "-")
    return r

def rut_canon(r: str) -> str:
    """
    Canoniza a '99999999-X' (sin ceros a la izquierda).
    NO valida DV aquí (opcional).
    """
    r = rut_compact(r).replace("-", "")
    if len(r) < 2:
        raise ValueError("Formato de RUT inválido.")
    cuerpo, dv = r[:-1], r[-1]
    cuerpo = str(int(cuerpo))  # elimina ceros a la izquierda (ej: '09396495' -> '9396495')
    return f"{cuerpo}-{dv}"

# -------------------------
# Login / Logout
# -------------------------
class AppLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        user = form.get_user()
        auth_login(self.request, user)

        vet = resolve_veterinaria_for_user(self.request, persist_default=user.is_superuser)
        if vet is None:
            auth_logout(self.request)
            form.add_error(None, "El usuario no tiene una veterinaria asociada.")
            return self.form_invalid(form)

        self.request.session[ACTIVE_VETERINARIA_SESSION_KEY] = vet.id
        self.request.veterinaria = vet
        return redirect(self.get_success_url())


class AppLogoutView(LogoutView):
    next_page = reverse_lazy("login")

# -------------------------
# Grilla clientes con filtros
# -------------------------
@login_required
def cliente_list(request):
    vet = current_veterinaria(request)
    qs = (
        cliente.objects
        .filter(veterinaria=vet)
        .select_related("comuna")
        .annotate(
            mascotas_nombres=StringAgg("mascota__nombre", delimiter=", ", distinct=True)
        )
        .all()
        .order_by("-created_at")
    )

    q = request.GET.get("q", "").strip()
    rut = request.GET.get("rut", "").strip()
    nombre = request.GET.get("nombre", "").strip()
    email = request.GET.get("email", "").strip()
    telefono = request.GET.get("telefono", "").strip()
    direccion = request.GET.get("direccion", "").strip()
    plansalud = request.GET.get("plansalud", "").strip()
    origen = request.GET.get("origen", "").strip()
    comuna_id = request.GET.get("comuna", "").strip()

    # 1) Búsqueda general (OR)
    if q:
        qs = qs.filter(
            Q(rut__icontains=q) |
            Q(nombre__icontains=q) |
            Q(email__icontains=q) |
            Q(telefono__icontains=q) |
            Q(direccion__icontains=q) |
            Q(plansalud__icontains=q) |
            Q(comuna__nombre__icontains=q) |
            Q(mascota__nombre__icontains=q)
        )

    # 2) Filtros específicos (AND)
    if rut:
        qs = qs.filter(rut__icontains=rut)
    if nombre:
        qs = qs.filter(
            Q(nombre__icontains=nombre) |
            Q(mascota__nombre__icontains=nombre)
        ).distinct()
    if email:
        qs = qs.filter(email__icontains=email)
    if telefono:
        qs = qs.filter(telefono__icontains=telefono)
    if direccion:
        qs = qs.filter(direccion__icontains=direccion)
    if plansalud:
        qs = qs.filter(plansalud__icontains=plansalud)
    if origen:
        qs = qs.filter(origen=origen)
    if comuna_id.isdigit():
        qs = qs.filter(comuna_id=int(comuna_id))

    # 3) Paginación
    paginator = Paginator(qs, 15)  # clientes por página
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    # 4) Mantener filtros en links de paginación (sin "page")
    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    context = {
        "clientes": page_obj,  # <- importante: ahora clientes ES un Page
        "page_obj": page_obj,
        "querystring": querystring,
        "comunas": comuna.objects.all().order_by("nombre"),
        "filters": {
            "q": q,
            "rut": rut,
            "nombre": nombre,
            "email": email,
            "telefono": telefono,
            "direccion": direccion,
            "plansalud": plansalud,
            "origen": origen,
            "comuna": comuna_id,
        }
    }
    return render(request, "cliente/cliente_list.html", context)

# -------------------------
# Cliente CRUD
# -------------------------
@login_required
def cliente_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.veterinaria = vet
            c.save()
            messages.success(request, "Cliente creado correctamente.")
            return redirect("mascotas_por_cliente", cliente_id=c.id)
    else:
        form = ClienteForm()
    return render(request, "cliente/cliente_form.html", {"form": form, "modo": "create"})

@login_required
def cliente_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(cliente, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = ClienteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("cliente_list")
    else:
        form = ClienteForm(instance=obj)
    return render(request, "cliente/cliente_form.html", {"form": form, "modo": "update", "obj": obj})

# -------------------------
# Mascotas por cliente
# -------------------------
@login_required
def mascota_create_cliente(request, cliente_id: int):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    if request.method == "POST":
        form = MascotaForm(request.POST)
        if form.is_valid():
            pet = form.save(commit=False)
            pet.cliente = c
            pet.save()
            return redirect("mascotas_por_cliente", cliente_id=c.id)
    else:
        form = MascotaForm()

    return render(request, "mascota/mascota_form.html", {
        "form": form,
        "cliente": c,
        "modo": "create",
    })

@login_required
def cliente_detail(request, cliente_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    mascotas = (
        mascota.objects
        .filter(cliente=c)
        .select_related("raza", "raza__especie")
        .order_by("nombre")
    )

    # Opcional: citas futuras (por si quieres mostrar un resumen)
    citas_proximas = (
        cita.objects
        .filter(mascota__cliente=c, estado_id=1)  # 1 = pendiente (ajusta si aplica)
        .select_related("mascota", "control", "estado")
        .order_by("fecha")[:10]
    )

    return render(
        request,
        "cliente/cliente_detail.html",
        {
            "cliente": c,
            "mascotas": mascotas,
            "citas_proximas": citas_proximas,
        },
    )

@login_required
def mascota_update(request, pk):
    vet = current_veterinaria(request)
    pet = get_object_or_404(mascota, pk=pk, cliente__veterinaria=vet)
    if request.method == "POST":
        form = MascotaForm(request.POST, instance=pet, veterinaria=vet)
        if form.is_valid():
            form.save()
            messages.success(request, "Mascota actualizada correctamente.")
            return redirect("mascotas_por_cliente", cliente_id=pet.cliente_id)
    else:
        form = MascotaForm(instance=pet, veterinaria=vet)

    return render(
            request,
            "mascota/mascota_form.html",
            {
                "form": form,
                "pet": pet,
                "cliente_id": pet.cliente_id,   # <- clave
                "cliente": pet.cliente,         # opcional
                "modo": "update",
            },
        )

# -------------------------
# Listar atenciones / citas por cliente
# -------------------------
@login_required
def atenciones_por_cliente(request, cliente_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)
    pets = mascota.objects.filter(cliente=c).select_related("raza", "raza__especie")
    atenciones = atencion.objects.filter(veterinaria=vet, mascota__cliente=c).select_related("mascota").order_by("-fechaatencion")
    return render(request, "atencion/atencion_list.html", {"cliente": c, "pets": pets, "atenciones": atenciones})

@login_required
def atencion_update(request, cliente_id: int, atencion_id: int):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    # Seguridad: obliga a que la atención pertenezca a una mascota de ese cliente
    a = get_object_or_404(atencion, pk=atencion_id, mascota__cliente=c, veterinaria=vet)

    if request.method == "POST":
        form = AtencionUpdateForm(request.POST, instance=a)
        if form.is_valid():
            form.save()  # updated_at se actualiza solo si auto_now=True
            messages.success(request, "Atención actualizada correctamente.")
            return redirect("atenciones_por_cliente", cliente_id=c.id)
    else:
        form = AtencionUpdateForm(instance=a)

    return render(request, "atencion/atencion_form_update.html", {
        "form": form,
        "cliente": c,
        "a": a,
    })

@login_required
def citas_por_cliente(request, cliente_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)
    pets = mascota.objects.filter(cliente=c).select_related("raza", "raza__especie")
    citas = cita.objects.filter(veterinaria=vet, mascota__cliente=c).select_related("mascota", "control", "estado").order_by("fecha")
    return render(request, "cita/cita_list.html", {"cliente": c, "pets": pets, "citas": citas})

# -------------------------
# Registro Atención (un solo formulario)
# atencion + detalles + próximas citas
# -------------------------
@login_required
def registrar_atencion(request, cliente_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    # Mascotas disponibles solo del cliente seleccionado
    mascotas_cliente = mascota.objects.filter(cliente=c).order_by("nombre")

    if request.method == "POST":
        # Pasamos cliente para que:
        # - filtre mascotas automáticamente
        # - el select muestre solo nombre (label_from_instance)
        a_form = AtencionForm(request.POST, cliente=c, veterinaria=vet)
        a_form.fields["mascota"].queryset = mascotas_cliente  # refuerzo

        d_formset = AtencionDetalleFormSet(request.POST, prefix="det", form_kwargs={"veterinaria": vet})
        c_formset = CitaFormSet(request.POST, prefix="cita", form_kwargs={"veterinaria": vet})

        if a_form.is_valid() and d_formset.is_valid() and c_formset.is_valid():
            with transaction.atomic():
                a = a_form.save(commit=False)
                a.veterinaria = vet
                a.save()  # fechaatencion auto_now_add

                # Detalles (inline con atención)
                d_formset.instance = a
                d_formset.save()

                # Próximas citas (opcional) - estado NO viene en el form, se fuerza a 1
                for form in c_formset:
                    if c_formset.can_delete and form.cleaned_data.get("DELETE"):
                        continue
                    if not form.cleaned_data:
                        continue

                    fecha = form.cleaned_data.get("fecha")
                    control = form.cleaned_data.get("control")

                    # Evita crear filas vacías:
                    if not (fecha and control):
                        continue

                    cit = form.save(commit=False)
                    cit.mascota = a.mascota
                    cit.veterinaria = vet
                    cit.estado_id = ESTADO_CITA_DEFAULT_ID
                    cit.save()

            messages.success(request, "Atención registrada correctamente (incluye detalles y próximas citas).")
            return redirect("atenciones_por_cliente", cliente_id=c.id)

    else:
        a_form = AtencionForm(cliente=c, veterinaria=vet)
        a_form.fields["mascota"].queryset = mascotas_cliente  # refuerzo

        d_formset = AtencionDetalleFormSet(prefix="det", form_kwargs={"veterinaria": vet})
        c_formset = CitaFormSet(prefix="cita", form_kwargs={"veterinaria": vet})

    context = {
        "cliente": c,
        "a_form": a_form,
        "d_formset": d_formset,
        "c_formset": c_formset,
    }
    return render(request, "atencion/atencion_form_unico.html", context)

# -------------------------
# Ficha Clínica (buscar por RUT)
# -------------------------
@login_required
def ficha_clinica_buscar(request):
    vet = current_veterinaria(request)
    rut_in = (request.GET.get("rut") or "").strip()
    cliente_obj = None

    if rut_in:
        try:
            rut_norm = rut_validate_and_format(rut_in)  # <- NORMALIZA AQUÍ
            cliente_obj = cliente.objects.filter(rut=rut_norm, veterinaria=vet).first()
            if not cliente_obj:
                messages.warning(request, "No existe un cliente con ese RUT.")
        except ValueError as e:
            messages.error(request, str(e))

    context = {
        "rut": rut_in,
        "cliente": cliente_obj,
        # ... lo demás que uses (mascotas, atenciones, etc.)
    }
    return render(request, "ficha/ficha_buscar.html", context)

@login_required
def atencion_detalle_view(request, atencion_id: int):
    vet = current_veterinaria(request)
    a = get_object_or_404(
        atencion.objects.select_related(
            "mascota", "mascota__cliente", "mascota__raza", "mascota__raza__especie"
        ),
        pk=atencion_id,
        veterinaria=vet,
    )

    detalles = (
        atenciondetalle.objects
        .select_related("prestacion")
        .filter(atencion=a)
        .order_by("created_at")
    )

    # Opcional: mostrar próximas citas de esa mascota (no son “de la atención”, pero suelen servir)
    proximas_citas = (
        cita.objects
        .select_related("control", "estado")
        .filter(veterinaria=vet, mascota=a.mascota)
        .order_by("fecha")
    )

    return render(request, "atencion/atencion_detalle.html", {
        "a": a,
        "detalles": detalles,
        "proximas_citas": proximas_citas,
    })


@login_required
def atenciondetalle_update(request, cliente_id: int, atencion_id: int, detalle_id: int):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)
    a = get_object_or_404(atencion, pk=atencion_id, mascota__cliente=c, veterinaria=vet)
    d = get_object_or_404(atenciondetalle, pk=detalle_id, atencion=a)

    if request.method == "POST":
        form = AtencionDetalleForm(request.POST, instance=d, veterinaria=vet)
        if form.is_valid():
            form.save()  # updated_at se setea solo con auto_now=True
            messages.success(request, "Prestación actualizada correctamente.")
            return redirect("atencion_detalle", a.id)
    else:
        form = AtencionDetalleForm(instance=d, veterinaria=vet)

    return render(request, "atencion/atenciondetalle_form.html", {
        "cliente": c,
        "a": a,
        "d": d,
        "form": form,
    })


@login_required
def atenciondetalle_delete(request, cliente_id: int, atencion_id: int, detalle_id: int):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)
    a = get_object_or_404(atencion, pk=atencion_id, mascota__cliente=c, veterinaria=vet)
    d = get_object_or_404(atenciondetalle, pk=detalle_id, atencion=a)

    if request.method == "POST":
        d.delete()
        messages.success(request, "Prestación eliminada correctamente.")
        return redirect("atencion_detalle", a.id)

    # Si llegara por GET, redirigimos (para no borrar por GET)
    return redirect("atencion_detalle", a.id)

@login_required
def mascotas_por_cliente(request, cliente_id: int):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)
    pets = (
        mascota.objects
        .select_related("raza", "raza__especie")
        .filter(cliente=c)
        .order_by("nombre")
    )
    return render(request, "mascota/mascota_list.html", {"cliente": c, "pets": pets})

@login_required
def ficha_clinica_mascota(request, mascota_id: int):
    vet = current_veterinaria(request)
    pet = get_object_or_404(
        mascota.objects.select_related("cliente", "raza", "raza__especie"),
        pk=mascota_id,
        cliente__veterinaria=vet,
    )

    # Trae todas las atenciones de la mascota, y prefetch de detalles
    detalles_qs = atenciondetalle.objects.select_related("prestacion").order_by("created_at")

    atenciones = (
        atencion.objects
        .filter(veterinaria=vet, mascota=pet)
        .prefetch_related(Prefetch("atenciondetalle_set", queryset=detalles_qs))
        .order_by("-fechaatencion")
    )

    return render(request, "ficha/ficha_mascota.html", {
        "pet": pet,
        "cliente": pet.cliente,
        "atenciones": atenciones,
    })

@login_required
def cita_estado_update(request, cliente_id, cita_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    # Garantiza que la cita pertenezca a una mascota del cliente
    cit = get_object_or_404(
        cita.objects.select_related("mascota", "estado", "control"),
        pk=cita_id,
        mascota__cliente=c,
        veterinaria=vet,
    )

    if request.method == "POST":
        form = CitaEstadoForm(request.POST, instance=cit)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado de la cita actualizado correctamente.")
            return redirect("citas_por_cliente", cliente_id=c.id)
    else:
        form = CitaEstadoForm(instance=cit)

    return render(request, "cita/cita_estado_form.html", {
        "cliente": c,
        "cita": cit,
        "form": form,
    })

# -------------------------
# ESPECIE
# -------------------------
@login_required
def especie_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = especie.objects.filter(veterinaria=vet).order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "catalogo/simple_list.html", {
        "title": "Especies",
        "q": q,
        "items": qs,
        "create_url": "especie_create",
        "update_url": "especie_update",
        "delete_url": "especie_delete",
        "show_especie": False,
    })

@login_required
def especie_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = EspecieForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Especie creada correctamente.")
            return redirect("especie_list")
    else:
        form = EspecieForm()

    return render(request, "catalogo/simple_form.html", {
        "title": "Nueva Especie",
        "form": form,
        "back_url": "especie_list",
    })


@login_required
def especie_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(especie, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = EspecieForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Especie actualizada correctamente.")
            return redirect("especie_list")
    else:
        form = EspecieForm(instance=obj)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Especie",
        "form": form,
        "back_url": "especie_list",
    })


@login_required
def especie_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(especie, pk=pk, veterinaria=vet)

    if request.method == "POST":
        # Protección lógica: si tiene razas asociadas, no borrar
        if raza.objects.filter(especie=obj).exists():
            messages.error(request, "No se puede eliminar la especie porque tiene razas asociadas.")
            return redirect("especie_list")

        try:
            obj.delete()
            messages.success(request, "Especie eliminada correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar la especie porque está en uso.")
        return redirect("especie_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Especie",
        "object_name": obj.nombre,
        "back_url": "especie_list",
    })

# -------------------------
# RAZA
# -------------------------
@login_required
def raza_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    especie_id = (request.GET.get("especie") or "").strip()

    qs = raza.objects.select_related("especie").filter(especie__veterinaria=vet).order_by("especie__nombre", "nombre")

    if especie_id:
        qs = qs.filter(especie_id=especie_id)

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) |
            Q(especie__nombre__icontains=q)
        )

    especies = especie.objects.filter(veterinaria=vet).order_by("nombre")

    return render(request, "catalogo/raza_list.html", {
        "title": "Razas",
        "q": q,
        "especie_id": especie_id,
        "items": qs,
        "especies": especies,
        "create_url": "raza_create",
        "update_url": "raza_update",
        "delete_url": "raza_delete",
    })


@login_required
def raza_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = RazaForm(request.POST, veterinaria=vet)
        if form.is_valid():
            form.save()
            messages.success(request, "Raza creada correctamente.")
            return redirect("raza_list")
    else:
        form = RazaForm(veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Nueva Raza",
        "form": form,
        "back_url": "raza_list",
    })


@login_required
def raza_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(raza, pk=pk, especie__veterinaria=vet)
    if request.method == "POST":
        form = RazaForm(request.POST, instance=obj, veterinaria=vet)
        if form.is_valid():
            form.save()
            messages.success(request, "Raza actualizada correctamente.")
            return redirect("raza_list")
    else:
        form = RazaForm(instance=obj, veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Raza",
        "form": form,
        "back_url": "raza_list",
    })


@login_required
def raza_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(raza.objects.select_related("especie"), pk=pk, especie__veterinaria=vet)

    if request.method == "POST":
        if mascota.objects.filter(raza=obj).exists():
            messages.error(request, "No se puede eliminar la raza porque tiene mascotas asociadas.")
            return redirect("raza_list")

        try:
            obj.delete()
            messages.success(request, "Raza eliminada correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar la raza porque está en uso.")
        return redirect("raza_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Raza",
        "object_name": f"{obj.nombre} ({obj.especie.nombre})",
        "back_url": "raza_list",
    })


# -------------------------
# PRESTACION
# -------------------------
@login_required
def prestacion_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = prestacion.objects.filter(veterinaria=vet).order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "catalogo/simple_list.html", {
        "title": "Prestaciones",
        "q": q,
        "items": qs,
        "create_url": "prestacion_create",
        "update_url": "prestacion_update",
        "delete_url": "prestacion_delete",
        "show_especie": False,
    })


@login_required
def prestacion_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = PrestacionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Prestación creada correctamente.")
            return redirect("prestacion_list")
    else:
        form = PrestacionForm()

    return render(request, "catalogo/simple_form.html", {
        "title": "Nueva Prestación",
        "form": form,
        "back_url": "prestacion_list",
    })


@login_required
def prestacion_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(prestacion, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = PrestacionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Prestación actualizada correctamente.")
            return redirect("prestacion_list")
    else:
        form = PrestacionForm(instance=obj)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Prestación",
        "form": form,
        "back_url": "prestacion_list",
    })


@login_required
def prestacion_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(prestacion, pk=pk, veterinaria=vet)

    if request.method == "POST":
        if atenciondetalle.objects.filter(prestacion=obj).exists():
            messages.error(request, "No se puede eliminar la prestación porque está utilizada en atenciones.")
            return redirect("prestacion_list")

        try:
            obj.delete()
            messages.success(request, "Prestación eliminada correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar la prestación porque está en uso.")
        return redirect("prestacion_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Prestación",
        "object_name": obj.nombre,
        "back_url": "prestacion_list",
    })


# -------------------------
# CONTROL
# -------------------------
@login_required
def control_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = control.objects.filter(veterinaria=vet).order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "catalogo/simple_list.html", {
        "title": "Controles",
        "q": q,
        "items": qs,
        "create_url": "control_create",
        "update_url": "control_update",
        "delete_url": "control_delete",
        "show_especie": False,
    })


@login_required
def control_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = ControlForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Control creado correctamente.")
            return redirect("control_list")
    else:
        form = ControlForm()

    return render(request, "catalogo/simple_form.html", {
        "title": "Nuevo Control",
        "form": form,
        "back_url": "control_list",
    })


@login_required
def control_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(control, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = ControlForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Control actualizado correctamente.")
            return redirect("control_list")
    else:
        form = ControlForm(instance=obj)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Control",
        "form": form,
        "back_url": "control_list",
    })


@login_required
def control_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(control, pk=pk, veterinaria=vet)

    if request.method == "POST":
        if cita.objects.filter(control=obj).exists():
            messages.error(request, "No se puede eliminar el control porque está utilizado en citas.")
            return redirect("control_list")

        try:
            obj.delete()
            messages.success(request, "Control eliminado correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar el control porque está en uso.")
        return redirect("control_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Control",
        "object_name": obj.nombre,
        "back_url": "control_list",
    })


# -------------------------
# ESTADOS (globales)
# -------------------------
@superusuario_required
def estadocliente_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = estadocliente.objects.order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "catalogo/simple_list.html", {
        "title": "Estados Cliente",
        "q": q,
        "items": qs,
        "create_url": "estadocliente_create",
        "update_url": "estadocliente_update",
        "delete_url": "estadocliente_delete",
        "show_especie": False,
    })


@superusuario_required
def estadocliente_create(request):
    if request.method == "POST":
        form = EstadoClienteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado cliente creado correctamente.")
            return redirect("estadocliente_list")
    else:
        form = EstadoClienteForm()

    return render(request, "catalogo/simple_form.html", {
        "title": "Nuevo Estado Cliente",
        "form": form,
        "back_url": "estadocliente_list",
    })


@superusuario_required
def estadocliente_update(request, pk):
    obj = get_object_or_404(estadocliente, pk=pk)
    if request.method == "POST":
        form = EstadoClienteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado cliente actualizado correctamente.")
            return redirect("estadocliente_list")
    else:
        form = EstadoClienteForm(instance=obj)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Estado Cliente",
        "form": form,
        "back_url": "estadocliente_list",
    })


@superusuario_required
def estadocliente_delete(request, pk):
    obj = get_object_or_404(estadocliente, pk=pk)

    if request.method == "POST":
        if cliente.objects.filter(estado=obj).exists():
            messages.error(request, "No se puede eliminar el estado porque está utilizado por clientes.")
            return redirect("estadocliente_list")

        try:
            obj.delete()
            messages.success(request, "Estado cliente eliminado correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar el estado porque está en uso.")
        return redirect("estadocliente_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Estado Cliente",
        "object_name": obj.nombre,
        "back_url": "estadocliente_list",
    })


@superusuario_required
def estadocita_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = estadocita.objects.order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)

    return render(request, "catalogo/simple_list.html", {
        "title": "Estados Cita",
        "q": q,
        "items": qs,
        "create_url": "estadocita_create",
        "update_url": "estadocita_update",
        "delete_url": "estadocita_delete",
        "show_especie": False,
    })


@superusuario_required
def estadocita_create(request):
    if request.method == "POST":
        form = EstadoCitaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado cita creado correctamente.")
            return redirect("estadocita_list")
    else:
        form = EstadoCitaForm()

    return render(request, "catalogo/simple_form.html", {
        "title": "Nuevo Estado Cita",
        "form": form,
        "back_url": "estadocita_list",
    })


@superusuario_required
def estadocita_update(request, pk):
    obj = get_object_or_404(estadocita, pk=pk)
    if request.method == "POST":
        form = EstadoCitaForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Estado cita actualizado correctamente.")
            return redirect("estadocita_list")
    else:
        form = EstadoCitaForm(instance=obj)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Estado Cita",
        "form": form,
        "back_url": "estadocita_list",
    })


@superusuario_required
def estadocita_delete(request, pk):
    obj = get_object_or_404(estadocita, pk=pk)

    if request.method == "POST":
        if cita.objects.filter(estado=obj).exists():
            messages.error(request, "No se puede eliminar el estado porque está utilizado por citas.")
            return redirect("estadocita_list")

        try:
            obj.delete()
            messages.success(request, "Estado cita eliminado correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar el estado porque está en uso.")
        return redirect("estadocita_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Estado Cita",
        "object_name": obj.nombre,
        "back_url": "estadocita_list",
    })

@login_required
@require_POST
def cita_delete(request, cliente_id, cita_id):
    vet = current_veterinaria(request)
    obj = get_object_or_404(cita, pk=cita_id, veterinaria=vet)

    # Seguridad: asegurar que la cita pertenece a una mascota del cliente
    if obj.mascota.cliente_id != cliente_id:
        messages.error(request, "No tienes permiso para eliminar esta cita.")
        return redirect("citas_por_cliente", cliente_id=cliente_id)

    obj.delete()
    messages.success(request, "Cita eliminada correctamente.")
    return redirect("citas_por_cliente", cliente_id=cliente_id)

@login_required
@require_POST
def atencion_delete(request, cliente_id, atencion_id):
    vet = current_veterinaria(request)
    a = get_object_or_404(atencion, pk=atencion_id, veterinaria=vet)

    # Seguridad: la atención debe ser de una mascota del cliente
    if a.mascota.cliente_id != cliente_id:
        messages.error(request, "No tienes permiso para eliminar esta atención.")
        return redirect("atenciones_por_cliente", cliente_id=cliente_id)

    with transaction.atomic():
        a.delete()

    messages.success(request, "Atención eliminada correctamente.")
    return redirect("atenciones_por_cliente", cliente_id=cliente_id)

@login_required
def mascota_delete_confirm(request, mascota_id):
    vet = current_veterinaria(request)
    m = get_object_or_404(mascota, pk=mascota_id, cliente__veterinaria=vet)
    # Conteos para advertencia
    total_citas = cita.objects.filter(mascota=m).count()
    total_atenciones = atencion.objects.filter(mascota=m).count()
    total_reservas = reserva.objects.filter(mascota=m).count()

    if request.method == "POST":
        # Regla sugerida: NO borrar si hay historial
        if total_citas > 0 or total_atenciones > 0 or total_reservas > 0:
            messages.error(
                request,
                "No se puede eliminar la mascota porque tiene citas, atenciones o reservas registradas."
            )
            return redirect("mascotas_por_cliente", cliente_id=m.cliente_id)

        cliente_id = m.cliente_id
        m.delete()
        messages.success(request, "Mascota eliminada correctamente.")
        return redirect("mascotas_por_cliente", cliente_id=cliente_id)

    return render(request, "mascota/mascota_confirm_delete.html", {
        "mascota": m,
        "total_citas": total_citas,
        "total_atenciones": total_atenciones,
        "total_reservas": total_reservas,
    })


@login_required
def cliente_delete_confirm(request, cliente_id):
    vet = current_veterinaria(request)
    c = get_object_or_404(cliente, pk=cliente_id, veterinaria=vet)

    # Conteos para advertencia: mascotas + historial (citas/atenciones de todas sus mascotas)
    mascotas_qs = mascota.objects.filter(cliente=c)
    total_mascotas = mascotas_qs.count()
    total_citas = cita.objects.filter(veterinaria=vet, mascota__cliente=c).count()
    total_atenciones = atencion.objects.filter(veterinaria=vet, mascota__cliente=c).count()
    total_reservas = reserva.objects.filter(veterinaria=vet, mascota__cliente=c).count()

    if request.method == "POST":
        # Regla sugerida: bloquear si hay historial (para no perder trazabilidad)
        if total_citas > 0 or total_atenciones > 0 or total_reservas > 0:
            messages.error(
                request,
                "No se puede eliminar el cliente porque existe historial (citas, atenciones o reservas) asociado."
            )
            return redirect("cliente_detail", cliente_id=c.id)  # o donde corresponda

        c.delete()  # OJO: cascada a mascotas (y lo que dependa de mascotas)
        messages.success(request, "Cliente eliminado correctamente.")
        return redirect("cliente_list")

    return render(request, "cliente/cliente_confirm_delete.html", {
        "cliente": c,
        "total_mascotas": total_mascotas,
        "total_citas": total_citas,
        "total_atenciones": total_atenciones,
        "total_reservas": total_reservas,
    })

@login_required
def dashboard_panel(request):
    vet = current_veterinaria(request)
    today = timezone.localdate()
    d7 = today - timedelta(days=6)     # incluye hoy => 7 días
    d30 = today - timedelta(days=29)   # incluye hoy => 30 días
    next2 = today + timedelta(days=2)
    reservas_hasta = today + timedelta(days=13)

    # Totales base
    total_clientes = cliente.objects.filter(veterinaria=vet).count()
    total_mascotas = mascota.objects.filter(cliente__veterinaria=vet).count()
    total_atenciones = atencion.objects.filter(veterinaria=vet).count()
    total_reservas = reserva.objects.filter(fecha__gte=today, veterinaria=vet).count()

    # Atenciones (hoy/7/30)
    atenciones_hoy = atencion.objects.filter(fechaatencion__date=today, veterinaria=vet).count()
    atenciones_7d = atencion.objects.filter(fechaatencion__date__gte=d7, veterinaria=vet).count()
    atenciones_30d = atencion.objects.filter(fechaatencion__date__gte=d30, veterinaria=vet).count()

    # Prestaciones (conteos)
    prestaciones_total = atenciondetalle.objects.filter(atencion__veterinaria=vet).count()
    prestaciones_30d = atenciondetalle.objects.filter(created_at__date__gte=d30, atencion__veterinaria=vet).count()
    prom_prest_por_atencion = (prestaciones_total / total_atenciones) if total_atenciones else 0

    # Top prestaciones (30 días)
    top_prestaciones_30d = (
        atenciondetalle.objects
        .filter(created_at__date__gte=d30, atencion__veterinaria=vet)
        .values("prestacion__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "prestacion__nombre")[:10]
    )

    # Citas (Pendiente = estado_id=1)
    citas_pendientes_total = cita.objects.filter(estado_id=1, veterinaria=vet).count()
    citas_hoy_pendientes = cita.objects.filter(estado_id=1, fecha=today, veterinaria=vet).count()

    citas_proximas_2d = (
        cita.objects
        .filter(estado_id=1, fecha__gte=today, fecha__lte=next2, veterinaria=vet)
        .select_related("mascota__cliente", "control")
        .order_by("fecha", "mascota__cliente__nombre", "mascota__nombre")[:20]
    )

    citas_vencidas = (
        cita.objects
        .filter(estado_id=1, fecha__lt=today, veterinaria=vet)
        .select_related("mascota__cliente", "control")
        .order_by("fecha", "mascota__cliente__nombre", "mascota__nombre")[:20]
    )

    # Controles más frecuentes en pendientes próximos 7 días
    next7 = today + timedelta(days=7)
    top_controles_7d = (
        cita.objects
        .filter(estado_id=1, fecha__gte=today, fecha__lte=next7, veterinaria=vet)
        .values("control__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "control__nombre")[:8]
    )

    # Series simples (para tabla): atenciones por día (últimos 7)
    atenciones_por_dia = (
        atencion.objects
        .filter(fechaatencion__date__gte=d7, veterinaria=vet)
        .annotate(d=TruncDate("fechaatencion"))
        .values("d")
        .annotate(total=Count("id"))
        .order_by("d")
    )
    # Normaliza días faltantes (para que siempre se vean 7)
    map_at = {x["d"]: x["total"] for x in atenciones_por_dia}
    serie_atenciones_7d = [{"fecha": d7 + timedelta(days=i), "total": map_at.get(d7 + timedelta(days=i), 0)} for i in range(7)]

    reservas_proximos_14_dias = list(
        reserva.objects
        .filter(fecha__gte=today, fecha__lte=reservas_hasta, veterinaria=vet)
        .select_related("mascota", "evento", "mascota__cliente")
        .order_by("fecha", "hora_inicio", "mascota__nombre")
    )
    reservas_por_fecha = {}
    for item in reservas_proximos_14_dias:
        reservas_por_fecha.setdefault(item.fecha, []).append(item)

    agenda_reservas_14d = [
        {
            "fecha": fecha,
            "items": reservas_por_fecha.get(fecha, []),
            "total": len(reservas_por_fecha.get(fecha, [])),
        }
        for fecha in (today + timedelta(days=i) for i in range(14))
    ]

    context = {
        "today": today,

        "total_clientes": total_clientes,
        "total_mascotas": total_mascotas,
        "total_atenciones": total_atenciones,
        "total_reservas": total_reservas,

        "atenciones_hoy": atenciones_hoy,
        "atenciones_7d": atenciones_7d,
        "atenciones_30d": atenciones_30d,

        "prestaciones_total": prestaciones_total,
        "prestaciones_30d": prestaciones_30d,
        "prom_prest_por_atencion": round(prom_prest_por_atencion, 2),
        "top_prestaciones_30d": top_prestaciones_30d,

        "citas_pendientes_total": citas_pendientes_total,
        "citas_hoy_pendientes": citas_hoy_pendientes,
        "citas_proximas_2d": citas_proximas_2d,
        "citas_vencidas": citas_vencidas,

        "top_controles_7d": top_controles_7d,
        "serie_atenciones_7d": serie_atenciones_7d,
        "agenda_reservas_14d": agenda_reservas_14d,
    }
    return render(request, "dashboard/panel.html", context)



@login_required
def citas_pendientes_filtrado(request):
    """Listado de citas pendientes con filtro por tipo de control."""
    vet = current_veterinaria(request)
    # Partimos de las citas pendientes
    qs = cita.objects.filter(estado_id=1, veterinaria=vet)

    # Filtro de búsqueda general (cliente, RUT, mascota)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(mascota__cliente__nombre__icontains=q) |
            Q(mascota__cliente__rut__icontains=q) |
            Q(mascota__nombre__icontains=q)
        )

    # Filtro por control (id recibido en GET)
    control_id = request.GET.get("control")
    if control_id and control_id.isdigit():
        qs = qs.filter(control_id=int(control_id))

    # Cargar relaciones y ordenar por fecha de cita ascendente
    qs = qs.select_related(
        "mascota", "mascota__cliente", "control", "estado"
    ).order_by("fecha", "mascota__cliente__nombre", "mascota__nombre")

    # Ordenar controles para la lista desplegable: prioritarios arriba
    prioridad = [
        "Vacunas", "Antipárasitario", "Peluqueria",
        "Control general", "Control dental",
    ]
    ordering = Case(
        *[When(nombre=nombre, then=Value(i)) for i, nombre in enumerate(prioridad)],
        default=Value(len(prioridad)),
        output_field=IntegerField(),
    )
    controles = control.objects.filter(veterinaria=vet).order_by(ordering, "nombre")

    paginator = Paginator(qs, 500)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "cita/citas_pendientes_filtrado.html", {
        "page_obj": page_obj,
        "citas": page_obj.object_list,
        "q": q,
        "control_id": control_id or "",
        "controles": controles,
    })

@login_required
def cita_update_global(request, cita_id: int):
    vet = current_veterinaria(request)
    obj = get_object_or_404(
        cita.objects.select_related("mascota", "mascota__cliente"),
        pk=cita_id,
        veterinaria=vet,
    )

    form = CitaUpdateForm(request.POST or None, instance=obj, veterinaria=vet)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("citas_pendientes_filtrado")

    return render(request, "cita/cita_form_global.html", {
        "form": form,
        "cita": obj,
    })

@login_required
@require_POST
def cita_delete_global(request, cita_id: int):
    vet = current_veterinaria(request)
    obj = get_object_or_404(cita, pk=cita_id, veterinaria=vet)

    if request.method == "POST":
        obj.estado_id = 3
        obj.save()
        return redirect("citas_pendientes_filtrado")

    return redirect("citas_pendientes_filtrado")

@login_required
@require_POST
def cita_check_global(request, cita_id: int):
    vet = current_veterinaria(request)
    obj = get_object_or_404(cita, pk=cita_id, veterinaria=vet)
    obj.estado_id = 2
    obj.save()
    return redirect("citas_pendientes_filtrado")


def reserva_publica_acceso(request):
    master_vet = veterinaria.objects.order_by("id").first()
    form = ReservaAccesoForm(request.POST or None)
    show_register = False
    registro_initial = None

    if request.method == "POST" and form.is_valid():
        rut = form.cleaned_data["rut"]
        email = form.cleaned_data["email"]
        cliente_obj = cliente.objects.filter(
            rut=rut,
            email__iexact=email,
            veterinaria=master_vet,
        ).first()

        if not cliente_obj:
            cliente_obj = cliente.objects.filter(rut=rut, veterinaria=master_vet).first()
            if cliente_obj:
                cliente_obj.email = email
                cliente_obj.save(update_fields=["email"])
                _clear_reserva_publica_session(request)
                request.session[RESERVA_CLIENTE_SESSION_KEY] = cliente_obj.id
                return redirect("reserva_publica_nueva")

            show_register = True
            registro_initial = {"rut": rut, "email": email}
            request.session[RESERVA_REGISTRO_SESSION_KEY] = registro_initial
            form.add_error(None, "No existe un cliente registrado con esos datos.")
        else:
            _clear_reserva_publica_session(request)
            request.session[RESERVA_CLIENTE_SESSION_KEY] = cliente_obj.id
            return redirect("reserva_publica_nueva")

    return render(request, "reserva/acceso_form.html", {
        "form": form,
        "show_register": show_register,
        "registro_initial": registro_initial,
        "hide_sidebar": True,
    })


def reserva_publica_registro(request):
    master_vet = get_master_veterinaria()
    registro_data = request.session.get(RESERVA_REGISTRO_SESSION_KEY, {}).copy()
    if not registro_data.get("rut") or not registro_data.get("email"):
        messages.error(request, "Primero debe validar su RUT y email para registrarse.")
        return redirect("reserva_publica_acceso")

    form = ReservaPublicaRegistroForm(request.POST or None, veterinaria=master_vet)

    if request.method == "POST" and form.is_valid():
        rut = registro_data["rut"]
        email = registro_data["email"]

        existente = cliente.objects.filter(rut=rut, veterinaria=master_vet).first()
        if existente:
            existente.email = email
            existente.save(update_fields=["email"])
            _clear_reserva_publica_session(request)
            request.session[RESERVA_CLIENTE_SESSION_KEY] = existente.id
            return redirect("reserva_publica_nueva")

        with transaction.atomic():
            cliente_obj = cliente.objects.create(
                veterinaria=master_vet,
                rut=rut,
                nombre=form.cleaned_data["nombre"],
                email=email,
                telefono=form.cleaned_data["telefono"],
                direccion=form.cleaned_data["direccion"],
                comuna=form.cleaned_data["comuna"],
                origen=OrigenCliente.WEB,
            )
            mascota.objects.create(
                cliente=cliente_obj,
                raza=form.cleaned_data["raza"],
                nombre=form.cleaned_data["nombre_mascota"],
                sexo=form.cleaned_data["sexo"],
                fechanac=form.cleaned_data["fechanac"],
            )

        _clear_reserva_publica_session(request)
        request.session[RESERVA_CLIENTE_SESSION_KEY] = cliente_obj.id
        messages.success(request, "Cliente y mascota registrados correctamente.")
        return redirect("reserva_publica_nueva")

    return render(request, "reserva/registro_form.html", {
        "form": form,
        "rut": registro_data["rut"],
        "email": registro_data["email"],
        "hide_sidebar": True,
    })


def reserva_publica_cambiar_cliente(request):
    _clear_reserva_publica_session(request, clear_cliente=True)
    return redirect("reserva_publica_acceso")


def reserva_publica_nueva(request):
    master_vet = get_master_veterinaria()
    cliente_obj = _get_reserva_cliente_publico(request)
    if not cliente_obj:
        messages.error(request, "Primero debe validar su RUT y email para continuar.")
        return redirect("reserva_publica_acceso")

    draft = request.session.get(RESERVA_DRAFT_SESSION_KEY, {})

    if request.method == "POST":
        form = ReservaPublicaBusquedaForm(request.POST, cliente_obj=cliente_obj, veterinaria=master_vet)
        if form.is_valid():
            request.session[RESERVA_DRAFT_SESSION_KEY] = {
                "mascota_id": form.cleaned_data["mascota"].id,
                "evento_id": form.cleaned_data["evento"].id,
                "fecha": form.cleaned_data["fecha"].isoformat(),
                "email_contacto": form.cleaned_data["email_contacto"],
                "observacion": form.cleaned_data["observacion"],
            }
            return redirect("reserva_publica_slots")
    else:
        initial = {}
        if draft:
            initial = {
                "mascota": draft.get("mascota_id"),
                "evento": draft.get("evento_id"),
                "fecha": draft.get("fecha"),
                "email_contacto": draft.get("email_contacto", cliente_obj.email),
                "observacion": draft.get("observacion", ""),
            }
        form = ReservaPublicaBusquedaForm(initial=initial, cliente_obj=cliente_obj, veterinaria=master_vet)

    return render(request, "reserva/reserva_form.html", {
        "form": form,
        "cliente": cliente_obj,
        "ventana_dias": VENTANA_RESERVA_DIAS,
        "hide_sidebar": True,
    })


def reserva_publica_slots(request):
    master_vet = get_master_veterinaria()
    cliente_obj = _get_reserva_cliente_publico(request)
    if not cliente_obj:
        messages.error(request, "Primero debe validar su RUT y email para continuar.")
        return redirect("reserva_publica_acceso")

    draft = _get_reserva_publica_draft(request, cliente_obj)
    if not draft:
        messages.error(request, "Debe completar primero los datos de la reserva.")
        return redirect("reserva_publica_nueva")

    slots = obtener_slots_disponibles(draft["evento"], draft["fecha"])
    form = ReservaSlotForm(request.POST or None, slots=slots)

    if request.method == "POST":
        if not slots:
            messages.error(request, "No hay horarios disponibles para la fecha seleccionada.")
            return redirect("reserva_publica_nueva")

        if form.is_valid():
            horario = next((slot for slot in slots if slot.id == form.cleaned_data["horario_id"]), None)
            if horario is None:
                form.add_error("horario_id", "Seleccione un horario valido.")
            else:
                obj = reserva(
                    veterinaria=master_vet,
                    mascota=draft["mascota"],
                    evento=draft["evento"],
                    fecha=draft["fecha"],
                    hora_inicio=horario.hora_inicio,
                    hora_fin=horario.hora_fin,
                    email_contacto=draft["email_contacto"],
                    observacion=draft["observacion"],
                )

                try:
                    obj.full_clean()
                except ValidationError as exc:
                    _add_validation_error_to_form(form, exc)
                else:
                    obj.save()
                    request.session.pop(RESERVA_DRAFT_SESSION_KEY, None)
                    messages.success(request, "Reserva creada correctamente.")
                    return redirect("reserva_publica_confirmacion", reserva_id=obj.id)

    return render(request, "reserva/slots_list.html", {
        "cliente": cliente_obj,
        "draft": draft,
        "slots": slots,
        "form": form,
        "hide_sidebar": True,
    })


def reserva_publica_confirmacion(request, reserva_id):
    master_vet = get_master_veterinaria()
    cliente_obj = _get_reserva_cliente_publico(request)
    if not cliente_obj:
        messages.error(request, "Primero debe validar su RUT y email para continuar.")
        return redirect("reserva_publica_acceso")

    obj = get_object_or_404(
        reserva.objects.select_related("mascota", "mascota__cliente", "evento"),
        pk=reserva_id,
        mascota__cliente=cliente_obj,
        veterinaria=master_vet,
    )

    return render(request, "reserva/confirmacion.html", {
        "cliente": cliente_obj,
        "reserva": obj,
        "hide_sidebar": True,
    })


@login_required
def agendaevento_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = (
        agendaevento.objects
        .filter(veterinaria=vet)
        .annotate(total_horarios=Count("horarios", distinct=True))
        .annotate(total_reservas=Count("reserva", distinct=True))
        .order_by("nombre")
    )

    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))

    return render(request, "agenda/evento_list.html", {
        "q": q,
        "items": qs,
    })


@login_required
def agendaevento_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = AgendaEventoForm(request.POST, veterinaria=vet)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Evento creado correctamente. Ahora configure los horarios disponibles.")
            return redirect("agendaeventohorario_list", evento_id=obj.id)
    else:
        form = AgendaEventoForm(veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Nuevo Evento Reservable",
        "form": form,
        "back_url": "agendaevento_list",
    })


@login_required
def agendaevento_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(agendaevento, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = AgendaEventoForm(request.POST, instance=obj, veterinaria=vet)
        if form.is_valid():
            form.save()
            messages.success(request, "Evento actualizado correctamente.")
            return redirect("agendaevento_list")
    else:
        form = AgendaEventoForm(instance=obj, veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Evento Reservable",
        "form": form,
        "back_url": "agendaevento_list",
    })


@login_required
def agendaevento_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(agendaevento, pk=pk, veterinaria=vet)

    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, "Evento eliminado correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar el evento porque tiene reservas asociadas.")
        return redirect("agendaevento_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Evento Reservable",
        "object_name": obj.nombre,
        "back_url": "agendaevento_list",
    })


@login_required
def agendaeventohorario_list(request, evento_id):
    vet = current_veterinaria(request)
    evento_obj = get_object_or_404(agendaevento, pk=evento_id, veterinaria=vet)
    items = evento_obj.horarios.filter(veterinaria=vet).order_by("dia_semana", "hora_inicio", "hora_fin")
    return render(request, "agenda/horario_list.html", {
        "evento": evento_obj,
        "items": items,
    })


@login_required
def agendaeventohorario_create(request, evento_id):
    vet = current_veterinaria(request)
    evento_obj = get_object_or_404(agendaevento, pk=evento_id, veterinaria=vet)
    if request.method == "POST":
        form = AgendaEventoHorarioForm(request.POST, evento=evento_obj, veterinaria=vet)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evento = evento_obj
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Horario creado correctamente.")
            return redirect("agendaeventohorario_list", evento_id=evento_obj.id)
    else:
        form = AgendaEventoHorarioForm(evento=evento_obj, veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": f"Nuevo Horario para {evento_obj.nombre}",
        "form": form,
        "back_url": "agendaeventohorario_list",
        "back_href": reverse("agendaeventohorario_list", args=[evento_obj.id]),
    })


@login_required
def agendaeventohorario_update(request, evento_id, pk):
    vet = current_veterinaria(request)
    evento_obj = get_object_or_404(agendaevento, pk=evento_id, veterinaria=vet)
    obj = get_object_or_404(agendaeventohorario, pk=pk, evento=evento_obj, veterinaria=vet)
    if request.method == "POST":
        form = AgendaEventoHorarioForm(request.POST, instance=obj, evento=evento_obj, veterinaria=vet)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evento = evento_obj
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Horario actualizado correctamente.")
            return redirect("agendaeventohorario_list", evento_id=evento_obj.id)
    else:
        form = AgendaEventoHorarioForm(instance=obj, evento=evento_obj, veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": f"Editar Horario de {evento_obj.nombre}",
        "form": form,
        "back_url": "agendaeventohorario_list",
        "back_href": reverse("agendaeventohorario_list", args=[evento_obj.id]),
    })


@login_required
def agendaeventohorario_delete(request, evento_id, pk):
    vet = current_veterinaria(request)
    evento_obj = get_object_or_404(agendaevento, pk=evento_id, veterinaria=vet)
    obj = get_object_or_404(agendaeventohorario, pk=pk, evento=evento_obj, veterinaria=vet)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Horario eliminado correctamente.")
        return redirect("agendaeventohorario_list", evento_id=evento_obj.id)

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Horario",
        "object_name": str(obj),
        "back_url": "agendaeventohorario_list",
        "back_href": reverse("agendaeventohorario_list", args=[evento_obj.id]),
    })


@login_required
def agendabloqueo_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = agendabloqueo.objects.filter(veterinaria=vet).order_by("-fecha_inicio", "hora_inicio", "titulo")

    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(motivo__icontains=q))

    return render(request, "agenda/bloqueo_list.html", {
        "q": q,
        "items": qs,
    })


@login_required
def agendabloqueo_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = AgendaBloqueoForm(request.POST, veterinaria=vet)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Bloqueo creado correctamente.")
            return redirect("agendabloqueo_list")
    else:
        form = AgendaBloqueoForm(veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Nuevo Bloqueo de Agenda",
        "form": form,
        "back_url": "agendabloqueo_list",
    })


@login_required
def agendabloqueo_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(agendabloqueo, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = AgendaBloqueoForm(request.POST, instance=obj, veterinaria=vet)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Bloqueo actualizado correctamente.")
            return redirect("agendabloqueo_list")
    else:
        form = AgendaBloqueoForm(instance=obj, veterinaria=vet)

    return render(request, "catalogo/simple_form.html", {
        "title": "Editar Bloqueo de Agenda",
        "form": form,
        "back_url": "agendabloqueo_list",
    })


@login_required
def agendabloqueo_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(agendabloqueo, pk=pk, veterinaria=vet)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Bloqueo eliminado correctamente.")
        return redirect("agendabloqueo_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Bloqueo de Agenda",
        "object_name": obj.titulo,
        "back_url": "agendabloqueo_list",
    })


@login_required
def reserva_list(request):
    vet = current_veterinaria(request)
    hoy = timezone.localdate()
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    evento_id = (request.GET.get("evento") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()

    qs = (
        reserva.objects
        .filter(fecha__gte=hoy, veterinaria=vet)
        .select_related("mascota", "mascota__cliente", "evento")
        .order_by("fecha", "hora_inicio", "mascota__nombre")
    )

    if q:
        qs = qs.filter(
            Q(mascota__nombre__icontains=q) |
            Q(mascota__cliente__nombre__icontains=q) |
            Q(mascota__cliente__rut__icontains=q) |
            Q(email_contacto__icontains=q)
        )

    if estado:
        qs = qs.filter(estado=estado)

    if evento_id.isdigit():
        qs = qs.filter(evento_id=int(evento_id))

    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)

    eventos = agendaevento.objects.filter(veterinaria=vet, activo=True).order_by("nombre")

    return render(request, "reserva/reserva_list.html", {
        "items": qs,
        "q": q,
        "estado": estado,
        "evento_id": evento_id,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "eventos": eventos,
        "estados": reserva._meta.get_field("estado").choices,
    })


@login_required
def reserva_update_estado(request, reserva_id):
    vet = current_veterinaria(request)
    obj = get_object_or_404(
        reserva.objects.select_related("mascota", "mascota__cliente", "evento"),
        pk=reserva_id,
        veterinaria=vet,
    )

    if request.method == "POST":
        form = ReservaEstadoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Reserva actualizada correctamente.")
            return redirect("reserva_list")
    else:
        form = ReservaEstadoForm(instance=obj)

    return render(request, "reserva/reserva_estado_form.html", {
        "form": form,
        "reserva": obj,
    })


@login_required
def promocion_list(request):
    vet = current_veterinaria(request)
    q = (request.GET.get("q") or "").strip()
    qs = promocion.objects.filter(veterinaria=vet)
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(descripcion__icontains=q) | Q(texto_correo__icontains=q))

    return render(request, "promocion/promocion_list.html", {
        "items": qs,
        "q": q,
        "veterinaria": vet,
    })


@login_required
def promocion_create(request):
    vet = current_veterinaria(request)
    if request.method == "POST":
        form = PromocionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.veterinaria = vet
            obj.save()
            messages.success(request, "Promocion guardada correctamente.")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return render(request, "promocion/modal_success.html")
            return render(request, "promocion/popup_success.html")
    else:
        form = PromocionForm()

    if request.GET.get("modal") == "1":
        return render(request, "promocion/promocion_form_modal.html", {
            "title": "Nueva Promocion",
            "form": form,
            "action_url": reverse("promocion_create"),
        })

    return render(request, "promocion/promocion_form.html", {
        "title": "Nueva Promocion",
        "form": form,
    })


@login_required
def promocion_update(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(promocion, pk=pk, veterinaria=vet)
    if request.method == "POST":
        form = PromocionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Promocion actualizada correctamente.")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return render(request, "promocion/modal_success.html")
            return render(request, "promocion/popup_success.html")
    else:
        form = PromocionForm(instance=obj)

    if request.GET.get("modal") == "1":
        return render(request, "promocion/promocion_form_modal.html", {
            "title": "Editar Promocion",
            "form": form,
            "promocion": obj,
            "action_url": reverse("promocion_update", args=[obj.id]),
        })

    return render(request, "promocion/promocion_form.html", {
        "title": "Editar Promocion",
        "form": form,
        "promocion": obj,
    })


@login_required
def promocion_detail(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(promocion, pk=pk, veterinaria=vet)
    if request.GET.get("modal") == "1":
        return render(request, "promocion/promocion_detail_modal.html", {"promocion": obj})
    return render(request, "promocion/promocion_detail.html", {"promocion": obj})


@login_required
def promocion_delete(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(promocion, pk=pk, veterinaria=vet)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Promocion eliminada correctamente.")
        return redirect("promocion_list")

    return render(request, "catalogo/confirm_delete.html", {
        "title": "Eliminar Promocion",
        "object_name": obj.titulo,
        "back_url": "promocion_list",
    })


def enviar_promocion_por_correo(promocion_obj, vet, destinatarios):
    connection = get_connection(
        host=vet.smtp_host,
        port=vet.smtp_port,
        username=vet.smtp_usuario or None,
        password=vet.smtp_password or None,
        use_tls=vet.smtp_usa_tls,
        use_ssl=vet.smtp_usa_ssl,
        fail_silently=False,
    )
    email = EmailMessage(
        subject=promocion_obj.titulo,
        body=promocion_obj.texto_correo,
        from_email=vet.correo,
        to=destinatarios,
        connection=connection,
    )
    email.send()


@login_required
@require_POST
def promocion_enviar_correo(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(promocion, pk=pk, veterinaria=vet)
    if vet is None or not vet.correo:
        messages.error(request, "Debe registrar una veterinaria con correo antes de enviar promociones.")
        return redirect("promocion_list")
    if not vet.smtp_host:
        messages.error(request, "Debe configurar el servidor SMTP de la veterinaria antes de enviar promociones.")
        return redirect("promocion_list")

    destinatarios = list(
        cliente.objects
        .filter(veterinaria=vet, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )
    if not destinatarios:
        messages.error(request, "No existen clientes con correo registrado.")
        return redirect("promocion_list")

    enviar_promocion_por_correo(obj, vet, destinatarios)
    messages.success(request, f"Promocion enviada a {len(destinatarios)} cliente(s).")
    return redirect("promocion_list")


@login_required
@require_POST
def promocion_enviar_prueba(request, pk):
    vet = current_veterinaria(request)
    obj = get_object_or_404(promocion, pk=pk, veterinaria=vet)
    correo_prueba = (request.POST.get("correo_prueba") or "").strip()

    if vet is None or not vet.correo:
        messages.error(request, "Debe registrar una veterinaria con correo antes de enviar promociones.")
        return redirect("promocion_list")
    if not vet.smtp_host:
        messages.error(request, "Debe configurar el servidor SMTP de la veterinaria antes de enviar promociones.")
        return redirect("promocion_list")
    if not correo_prueba:
        messages.error(request, "Debe indicar un correo de prueba.")
        return redirect("promocion_list")

    vet.correo_prueba = correo_prueba
    vet.save(update_fields=["correo_prueba"])
    enviar_promocion_por_correo(obj, vet, [correo_prueba])
    messages.success(request, f"Correo de prueba enviado a {correo_prueba}.")
    return redirect("promocion_list")


@login_required
def veterinaria_list(request):
    if not (usuario_es_superusuario(request.user) or usuario_es_administrador(request.user)):
        raise PermissionDenied

    if request.user.is_superuser:
        veterinarias = veterinaria.objects.order_by("nombre", "id")
        active_id = request.session.get(ACTIVE_VETERINARIA_SESSION_KEY)
    else:
        vet = current_veterinaria(request)
        veterinarias = veterinaria.objects.filter(pk=vet.pk).order_by("nombre", "id")
        active_id = vet.id
    return render(request, "veterinaria/veterinaria_list.html", {
        "items": veterinarias,
        "active_id": active_id,
    })


@login_required
def veterinaria_create(request):
    if not usuario_es_superusuario(request.user):
        raise PermissionDenied

    if request.method == "POST":
        form = VeterinariaForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Veterinaria creada correctamente.")
            return redirect("veterinaria_list")
    else:
        form = VeterinariaForm()

    return render(request, "promocion/veterinaria_form.html", {
        "form": form,
        "title": "Nueva Veterinaria",
        "back_url": "veterinaria_list",
    })


@login_required
def veterinaria_update(request, pk):
    if not (usuario_es_superusuario(request.user) or usuario_es_administrador(request.user)):
        raise PermissionDenied

    if request.user.is_superuser:
        obj = get_object_or_404(veterinaria, pk=pk)
    else:
        vet = current_veterinaria(request)
        if pk != vet.id:
            raise PermissionDenied
        obj = vet
    if request.method == "POST":
        form = VeterinariaForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos de veterinaria guardados correctamente.")
            return redirect("veterinaria_list")
    else:
        form = VeterinariaForm(instance=obj)

    return render(request, "promocion/veterinaria_form.html", {"form": form, "title": "Editar Veterinaria", "back_url": "veterinaria_list"})


@login_required
def veterinaria_set_active(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method != "POST":
        return redirect("veterinaria_list")

    veterinaria_id = request.POST.get("veterinaria_id")
    next_url = request.POST.get("next") or reverse("veterinaria_list")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("veterinaria_list")
    vet = get_object_or_404(veterinaria, pk=veterinaria_id)
    set_active_veterinaria(request, vet, persist_default=True)
    messages.success(request, f"Veterinaria activa actualizada a {vet.nombre}.")
    return redirect(next_url)
