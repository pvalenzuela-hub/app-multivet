from datetime import time, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core import mail
from django.contrib.auth.models import Group
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    agendabloqueo,
    agendaevento,
    agendaeventohorario,
    EstadoReserva,
    cliente,
    comuna,
    cita,
    control,
    especie,
    estadocita,
    estadocliente,
    mascota,
    OrigenCliente,
    obtener_slots_disponibles,
    promocion,
    prestacion,
    raza,
    reserva,
    veterinaria,
)
from .utils.rut import rut_dv


RESERVA_PUBLICA_SESSION_PREFIX = "reserva_publica"
RESERVA_PUBLICA_CLIENTE_SUFFIX = "cliente_id"
RESERVA_PUBLICA_DRAFT_SUFFIX = "draft"
RESERVA_PUBLICA_REGISTRO_SUFFIX = "registro"


class ReservaBaseMixin:
    @classmethod
    def setUpTestData(cls):
        cls.hoy = timezone.localdate()
        cls.manana = cls.hoy + timedelta(days=1)

        cls.veterinaria = veterinaria.objects.order_by("id").first()
        if cls.veterinaria is None:
            cls.veterinaria = veterinaria.objects.create(
                nombre="Vet Test",
                correo="test@vet.local",
                smtp_host="",
                smtp_port=587,
                smtp_usuario="",
                smtp_password="",
            )
        cls.comuna = comuna.objects.create(nombre="Santiago")
        cls.estado_cliente = estadocliente.objects.create(nombre="Activo")
        cls.especie = especie.objects.create(nombre="Canino", veterinaria=cls.veterinaria)
        cls.raza = raza.objects.create(nombre="Mestizo", especie=cls.especie)

        rut_1 = f"12345678-{rut_dv('12345678')}"
        rut_2 = f"87654321-{rut_dv('87654321')}"

        cls.cliente = cliente.objects.create(
            veterinaria=cls.veterinaria,
            rut=rut_1,
            nombre="Ana Cliente",
            email="ana@example.com",
            telefono="999999999",
            direccion="Av. Siempre Viva 123",
            comuna=cls.comuna,
            estado=cls.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )
        cls.otro_cliente = cliente.objects.create(
            veterinaria=cls.veterinaria,
            rut=rut_2,
            nombre="Beto Cliente",
            email="beto@example.com",
            telefono="888888888",
            direccion="Otra calle 456",
            comuna=cls.comuna,
            estado=cls.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )

        cls.mascota = mascota.objects.create(
            cliente=cls.cliente,
            raza=cls.raza,
            nombre="Luna",
        )
        cls.otra_mascota = mascota.objects.create(
            cliente=cls.otro_cliente,
            raza=cls.raza,
            nombre="Toby",
        )

        cls.evento = agendaevento.objects.create(nombre="Examen de sangre", veterinaria=cls.veterinaria)
        cls.horario = agendaeventohorario.objects.create(
            evento=cls.evento,
            veterinaria=cls.veterinaria,
            dia_semana=cls.manana.weekday(),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
        )

    def validar_cliente_publico(self, cliente_obj=None, email=None):
        cliente_obj = cliente_obj or self.cliente
        return self.client.post(reverse("reserva_publica_acceso", args=[self.veterinaria.reserva_publica_token]), {
            "rut": cliente_obj.rut,
            "email": email or cliente_obj.email,
        })

    def reserva_publica_session_key(self, suffix):
        return f"{RESERVA_PUBLICA_SESSION_PREFIX}:{self.veterinaria.reserva_publica_token}:{suffix}"


class LoginTemplateTests(TestCase):
    def test_root_redirige_a_login_si_no_autenticado(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("login"))

    def test_login_renderiza_logo_nuevo(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertContains(response, "alt=\"Vetnex\"")
        self.assertContains(response, "Controla tu veterinaria")
        self.assertContains(response, "Usá tu RUT y contraseña")

    def test_login_y_home_renderizan_logo(self):
        user = get_user_model().objects.create_user(username="login_smoke", password="secret123")

        login_response = self.client.get(reverse("login"))
        self.client.force_login(user)
        home_response = self.client.get(reverse("cliente_list"))

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(login_response, "vetnex-logo.svg")
        self.assertContains(home_response, "vetnex-logo.svg")

    def test_logout_en_home_se_renderiza_como_post(self):
        user = get_user_model().objects.create_user(username="logout_smoke", password="secret123")
        self.client.force_login(user)

        response = self.client.get(reverse("cliente_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/logout/"')
        self.assertEqual(response.content.decode().count('action="/logout/"'), 3)

    def test_login_redirige_a_panel(self):
        user = get_user_model().objects.create_user(username="panel_login", password="secret123")

        response = self.client.post(reverse("login"), {
            "username": "panel_login",
            "password": "secret123",
        })

        self.assertRedirects(response, reverse("dashboard_panel"))

    def test_root_redirige_a_panel_si_autenticado(self):
        user = get_user_model().objects.create_user(username="root_panel", password="secret123")
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("dashboard_panel"))


class EstadoCatalogoTests(ReservaBaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.superuser = get_user_model().objects.create_superuser(
            username="estado_super",
            email="estado_super@example.com",
            password="secret123",
        )
        cls.regular_user = get_user_model().objects.create_user(
            username="estado_user",
            password="secret123",
        )
        cls.control = control.objects.create(veterinaria=cls.veterinaria, nombre="Control general")

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_acceso_solo_superuser(self):
        self.client.force_login(self.regular_user)

        self.assertEqual(self.client.get(reverse("estadocliente_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("estadocita_list")).status_code, 403)

    def test_crud_estado_cliente_superuser(self):
        response = self.client.get(reverse("estadocliente_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estados Cliente")

        response = self.client.post(reverse("estadocliente_create"), {"nombre": "Suspendido"})
        self.assertRedirects(response, reverse("estadocliente_list"))

        estado = estadocliente.objects.get(nombre="Suspendido")
        response = self.client.post(reverse("estadocliente_update", args=[estado.id]), {"nombre": "Revisado"})
        self.assertRedirects(response, reverse("estadocliente_list"))
        estado.refresh_from_db()
        self.assertEqual(estado.nombre, "Revisado")

        response = self.client.post(reverse("estadocliente_delete", args=[estado.id]))
        self.assertRedirects(response, reverse("estadocliente_list"))
        self.assertFalse(estadocliente.objects.filter(id=estado.id).exists())

    def test_crud_estado_cita_superuser(self):
        response = self.client.get(reverse("estadocita_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estados Cita")

        response = self.client.post(reverse("estadocita_create"), {"nombre": "Reprogramada"})
        self.assertRedirects(response, reverse("estadocita_list"))

        estado = estadocita.objects.get(nombre="Reprogramada")
        response = self.client.post(reverse("estadocita_update", args=[estado.id]), {"nombre": "Reagendada"})
        self.assertRedirects(response, reverse("estadocita_list"))
        estado.refresh_from_db()
        self.assertEqual(estado.nombre, "Reagendada")

        response = self.client.post(reverse("estadocita_delete", args=[estado.id]))
        self.assertRedirects(response, reverse("estadocita_list"))
        self.assertFalse(estadocita.objects.filter(id=estado.id).exists())

    def test_no_elimina_estado_cliente_en_uso(self):
        estado = estadocliente.objects.create(nombre="En revision")
        cliente.objects.create(
            veterinaria=self.veterinaria,
            rut=f"23456789-{rut_dv('23456789')}",
            nombre="Cliente Estado",
            email="cliente.estado@example.com",
            telefono="777777777",
            direccion="Calle Estado 123",
            comuna=self.comuna,
            estado=estado,
            origen=OrigenCliente.SISTEMA,
        )

        response = self.client.post(reverse("estadocliente_delete", args=[estado.id]))

        self.assertRedirects(response, reverse("estadocliente_list"))
        self.assertTrue(estadocliente.objects.filter(id=estado.id).exists())

    def test_no_elimina_estado_cita_en_uso(self):
        estado = estadocita.objects.create(nombre="Revisada")
        cita.objects.create(
            mascota=self.mascota,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            control=self.control,
            observacion="",
            estado=estado,
        )

        response = self.client.post(reverse("estadocita_delete", args=[estado.id]))

        self.assertRedirects(response, reverse("estadocita_list"))
        self.assertTrue(estadocita.objects.filter(id=estado.id).exists())


class ProductionSeedCommandTests(TestCase):
    def test_seed_production_reemplaza_demo_y_deja_base(self):
        out = StringIO()
        call_command(
            "seed_production",
            stdout=out,
            nombre="Vetnex",
            correo="contacto@vetnex.cl",
            logo_url="https://cdn.example.com/vetnex-logo.svg",
        )

        vet = veterinaria.objects.get(pk=1)

        self.assertEqual(vet.nombre, "Vetnex")
        self.assertEqual(vet.correo, "contacto@vetnex.cl")
        self.assertEqual(vet.logo, "https://cdn.example.com/vetnex-logo.svg")
        self.assertTrue(estadocliente.objects.filter(pk=1, nombre="Activo").exists())
        self.assertTrue(estadocita.objects.filter(pk=1, nombre="Pendiente").exists())
        self.assertFalse(cliente.objects.filter(rut="22222222-2").exists())
        self.assertTrue(control.objects.filter(veterinaria=vet, nombre="Control general").exists())
        self.assertTrue(prestacion.objects.filter(veterinaria=vet, nombre="Consulta general").exists())
        self.assertFalse(control.objects.filter(veterinaria=vet, nombre="Control demo").exists())
        self.assertFalse(prestacion.objects.filter(veterinaria=vet, nombre="Consulta demo").exists())
        nuevo_estado_cliente = estadocliente.objects.create(nombre="Temporal Cliente")
        nuevo_estado_cita = estadocita.objects.create(nombre="Temporal Cita")
        self.assertNotEqual(nuevo_estado_cliente.id, 1)
        self.assertNotEqual(nuevo_estado_cita.id, 1)
        self.assertIn("Seed de produccion aplicado correctamente.", out.getvalue())


class ReservaPublicaFlowTests(ReservaBaseMixin, TestCase):
    def test_formulario_publico_renderiza_descripcion_del_evento_en_select(self):
        self.evento.descripcion = "Ayuno requerido antes del examen"
        self.evento.save(update_fields=["descripcion"])
        self.validar_cliente_publico()

        response = self.client.get(reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")
        self.assertContains(response, 'data-descripcion="Ayuno requerido antes del examen"', html=False)

    def test_acceso_publico_valido_guarda_cliente_en_sesion(self):
        response = self.validar_cliente_publico()

        self.assertRedirects(response, reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]))
        self.assertEqual(
            self.client.session.get(self.reserva_publica_session_key(RESERVA_PUBLICA_CLIENTE_SUFFIX)),
            self.cliente.id,
        )

    def test_acceso_publico_rechaza_email_incorrecto(self):
        response = self.validar_cliente_publico(email="otro@example.com")

        self.assertRedirects(response, reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, "otro@example.com")
        self.assertEqual(
            self.client.session.get(self.reserva_publica_session_key(RESERVA_PUBLICA_CLIENTE_SUFFIX)),
            self.cliente.id,
        )

    def test_acceso_publico_muestra_registro_si_rut_no_existe(self):
        response = self.client.post(reverse("reserva_publica_acceso", args=[self.veterinaria.reserva_publica_token]), {
            "rut": f"11111111-{rut_dv('11111111')}",
            "email": "nuevo@example.com",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")
        self.assertContains(response, "Registrarme")
        self.assertEqual(
            self.client.session.get(self.reserva_publica_session_key(RESERVA_PUBLICA_REGISTRO_SUFFIX)),
            {"rut": f"11111111-{rut_dv('11111111')}", "email": "nuevo@example.com"},
        )

    def test_registro_publico_crea_cliente_web_y_mascota(self):
        rut_nuevo = f"11111111-{rut_dv('11111111')}"
        session = self.client.session
        session[self.reserva_publica_session_key(RESERVA_PUBLICA_REGISTRO_SUFFIX)] = {"rut": rut_nuevo, "email": "nuevo@example.com"}
        session.save()

        response = self.client.post(reverse("reserva_publica_registro", args=[self.veterinaria.reserva_publica_token]), {
            "nombre": "Cliente Web",
            "telefono": "777777777",
            "direccion": "Direccion Web 123",
            "comuna": self.comuna.id,
            "raza": self.raza.id,
            "nombre_mascota": "Kiara",
            "sexo": "H",
            "fechanac": "",
        })

        nuevo_cliente = cliente.objects.get(rut=rut_nuevo)
        nueva_mascota = mascota.objects.get(cliente=nuevo_cliente)

        self.assertRedirects(response, reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]))
        self.assertEqual(nuevo_cliente.origen, OrigenCliente.WEB)
        self.assertEqual(nuevo_cliente.email, "nuevo@example.com")
        self.assertEqual(nueva_mascota.nombre, "Kiara")
        self.assertEqual(
            self.client.session.get(self.reserva_publica_session_key(RESERVA_PUBLICA_CLIENTE_SUFFIX)),
            nuevo_cliente.id,
        )

    def test_registro_publico_redirige_a_existente_si_rut_ya_existe(self):
        session = self.client.session
        session[self.reserva_publica_session_key(RESERVA_PUBLICA_REGISTRO_SUFFIX)] = {"rut": self.cliente.rut, "email": "actualizado@example.com"}
        session.save()

        response = self.client.post(reverse("reserva_publica_registro", args=[self.veterinaria.reserva_publica_token]), {
            "nombre": "No importa",
            "telefono": "123",
            "direccion": "X",
            "comuna": self.comuna.id,
            "raza": self.raza.id,
            "nombre_mascota": "Nueva",
            "sexo": "M",
            "fechanac": "",
        })

        self.assertRedirects(response, reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, "actualizado@example.com")
        self.assertEqual(mascota.objects.filter(cliente=self.cliente).count(), 1)

    def test_registro_publico_sin_contexto_redirige_a_acceso(self):
        response = self.client.get(reverse("reserva_publica_registro", args=[self.veterinaria.reserva_publica_token]))

        self.assertRedirects(response, reverse("reserva_publica_acceso", args=[self.veterinaria.reserva_publica_token]))

    def test_flujo_publico_crea_reserva_y_no_modifica_email_del_cliente(self):
        self.validar_cliente_publico()

        response = self.client.post(reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]), {
            "mascota": self.mascota.id,
            "evento": self.evento.id,
            "fecha": self.manana.isoformat(),
            "email_contacto": "recordatorios@example.com",
            "observacion": "Ayuno de 8 horas",
        })
        self.assertRedirects(response, reverse("reserva_publica_slots", args=[self.veterinaria.reserva_publica_token]))

        response = self.client.get(reverse("reserva_publica_slots", args=[self.veterinaria.reserva_publica_token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")

        response = self.client.post(reverse("reserva_publica_slots", args=[self.veterinaria.reserva_publica_token]), {
            "horario_id": self.horario.id,
        })

        creada = reserva.objects.get()
        self.assertRedirects(response, reverse("reserva_publica_confirmacion", args=[self.veterinaria.reserva_publica_token, creada.id]))

        response = self.client.get(reverse("reserva_publica_confirmacion", args=[self.veterinaria.reserva_publica_token, creada.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")
        self.assertEqual(creada.mascota, self.mascota)
        self.assertEqual(creada.evento, self.evento)
        self.assertEqual(creada.email_contacto, "recordatorios@example.com")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, "ana@example.com")

    def test_formulario_publico_no_acepta_reservar_para_mascota_de_otro_cliente(self):
        self.validar_cliente_publico()

        response = self.client.post(reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]), {
            "mascota": self.otra_mascota.id,
            "evento": self.evento.id,
            "fecha": self.manana.isoformat(),
            "email_contacto": self.cliente.email,
            "observacion": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "id_mascota_error")
        self.assertIsNone(self.client.session.get(self.reserva_publica_session_key(RESERVA_PUBLICA_DRAFT_SUFFIX)))

    def test_formulario_publico_rechaza_fecha_hoy(self):
        self.validar_cliente_publico()

        response = self.client.post(reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]), {
            "mascota": self.mascota.id,
            "evento": self.evento.id,
            "fecha": self.hoy.isoformat(),
            "email_contacto": self.cliente.email,
            "observacion": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dia siguiente")
        self.assertEqual(reserva.objects.count(), 0)

    def test_formulario_publico_rechaza_fecha_mayor_a_dos_semanas(self):
        self.validar_cliente_publico()
        fecha_fuera_de_rango = self.manana + timedelta(days=14)

        response = self.client.post(reverse("reserva_publica_nueva", args=[self.veterinaria.reserva_publica_token]), {
            "mascota": self.mascota.id,
            "evento": self.evento.id,
            "fecha": fecha_fuera_de_rango.isoformat(),
            "email_contacto": self.cliente.email,
            "observacion": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "proximos 14 dias")
        self.assertEqual(reserva.objects.count(), 0)

    def test_link_publico_con_token_usa_contexto_correcto(self):
        otra_veterinaria = veterinaria.objects.create(
            nombre="Vet Link",
            correo="link@vet.local",
            smtp_host="",
            smtp_port=587,
            smtp_usuario="",
            smtp_password="",
        )
        otra_especie = especie.objects.create(nombre="Felino Link", veterinaria=otra_veterinaria)
        otra_raza = raza.objects.create(nombre="Mestizo Link", especie=otra_especie)
        otra_cliente = cliente.objects.create(
            veterinaria=otra_veterinaria,
            rut=f"11111111-{rut_dv('11111111')}",
            nombre="Cliente Link",
            email="link@example.com",
            telefono="777777777",
            direccion="Link 123",
            comuna=self.comuna,
            estado=self.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )
        otra_mascota = mascota.objects.create(cliente=otra_cliente, raza=otra_raza, nombre="Mishi Link")
        otra_evento = agendaevento.objects.create(nombre="Consulta Link", veterinaria=otra_veterinaria)

        response = self.client.get(reverse("reserva_publica_acceso", args=[otra_veterinaria.reserva_publica_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")

        response = self.client.post(reverse("reserva_publica_acceso", args=[otra_veterinaria.reserva_publica_token]), {
            "rut": otra_cliente.rut,
            "email": otra_cliente.email,
        })

        self.assertRedirects(response, reverse("reserva_publica_nueva", args=[otra_veterinaria.reserva_publica_token]))

        response = self.client.get(reverse("reserva_publica_nueva", args=[otra_veterinaria.reserva_publica_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vetnex-logo.svg")
        self.assertNotContains(response, "PetSalud")
        self.assertContains(response, otra_evento.nombre)
        self.assertContains(response, otra_mascota.nombre)
        self.assertNotContains(response, self.evento.nombre)
        self.assertNotContains(response, self.mascota.nombre)


class DisponibilidadReservaTests(ReservaBaseMixin, TestCase):
    def test_horario_permite_mismo_slot_en_eventos_distintos(self):
        otro_evento = agendaevento.objects.create(nombre="Vacunacion", veterinaria=self.veterinaria)

        horario = agendaeventohorario(
            evento=otro_evento,
            veterinaria=self.veterinaria,
            dia_semana=self.manana.weekday(),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
        )

        horario.full_clean()

    def test_obtener_slots_disponibles_excluye_bloqueos(self):
        agendabloqueo.objects.create(
            titulo="Vacaciones",
            veterinaria=self.veterinaria,
            fecha_inicio=self.manana,
            fecha_fin=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
        )

        slots = obtener_slots_disponibles(self.evento, self.manana)

        self.assertEqual(slots, [])

    def test_reserva_no_permite_doble_toma_del_mismo_slot(self):
        reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )

        duplicada = reserva(
            mascota=self.otra_mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="beto@example.com",
        )

        with self.assertRaises(ValidationError):
            duplicada.full_clean()

    def test_reserva_permite_mismo_slot_en_eventos_distintos(self):
        otro_evento = agendaevento.objects.create(nombre="Vacunacion", veterinaria=self.veterinaria)
        agendaeventohorario.objects.create(
            evento=otro_evento,
            veterinaria=self.veterinaria,
            dia_semana=self.manana.weekday(),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
        )
        reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )

        paralela = reserva(
            mascota=self.otra_mascota,
            evento=otro_evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="beto@example.com",
        )

        paralela.full_clean()


class ReservaGestionTests(ReservaBaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = get_user_model().objects.create_user(
            username="tester",
            password="secret123",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_gestion_reserva_actualiza_estado(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.post(reverse("reserva_update_estado", args=[obj.id]), {
            "estado": "confirmada",
            "observacion": "Cliente confirmado por telefono",
        })

        obj.refresh_from_db()
        self.assertRedirects(response, reverse("reserva_list"))
        self.assertEqual(obj.estado, "confirmada")
        self.assertEqual(obj.observacion, "Cliente confirmado por telefono")

    def test_regresion_guardado_estado_reserva_no_falla(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.post(reverse("reserva_update_estado", args=[obj.id]), {
            "estado": "cancelada",
            "observacion": "Prueba de regresion",
        })

        obj.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.estado, "cancelada")
        self.assertEqual(obj.observacion, "Prueba de regresion")

    def test_formulario_gestion_reserva_renderiza(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.get(reverse("reserva_update_estado", args=[obj.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestionar Reserva")
        self.assertContains(response, "form")
        self.assertContains(response, "Pendiente")
        self.assertContains(response, "Confirmada")
        self.assertContains(response, "Cancelada")

    def test_gestion_reserva_no_rompe_flujo_con_slot_ya_tomado(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )
        reserva.objects.create(
            mascota=self.otra_mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="beto@example.com",
            estado="cancelada",
        )

        response = self.client.post(reverse("reserva_update_estado", args=[obj.id]), {
            "estado": "cancelada",
            "observacion": "Cancelada por solicitud del cliente",
        })

        obj.refresh_from_db()
        self.assertRedirects(response, reverse("reserva_list"))
        self.assertEqual(obj.estado, "cancelada")

    def test_listado_reservas_muestra_solo_hoy_en_adelante(self):
        pasada = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.hoy - timedelta(days=1),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )
        vigente = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(11, 0),
            hora_fin=time(11, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.get(reverse("reserva_list"))

        items = list(response.context["items"])
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(pasada, items)
        self.assertIn(vigente, items)

    def test_panel_cuenta_solo_reservas_desde_hoy(self):
        reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.hoy - timedelta(days=1),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="ana@example.com",
        )
        vigente = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(11, 0),
            hora_fin=time(11, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.get(reverse("dashboard_panel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_reservas"], 1)
        self.assertIn(vigente, response.context["agenda_reservas_14d"][1]["items"])

    def test_agenda_hoy_muestra_solo_reservas_pendientes(self):
        pendiente = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.hoy,
            hora_inicio=time(9, 0),
            hora_fin=time(9, 30),
            email_contacto="ana@example.com",
        )
        reserva.objects.create(
            mascota=self.otra_mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.hoy,
            hora_inicio=time(10, 0),
            hora_fin=time(10, 30),
            email_contacto="beto@example.com",
            estado=EstadoReserva.CONFIRMADA,
        )
        reserva.objects.create(
            mascota=self.otra_mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.hoy,
            hora_inicio=time(11, 0),
            hora_fin=time(11, 30),
            email_contacto="beto@example.com",
            estado=EstadoReserva.CANCELADA,
        )

        response = self.client.get(reverse("agenda_hoy"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reservas_hoy_total"], 3)
        self.assertEqual(response.context["reservas_pendientes_hoy_total"], 1)
        self.assertEqual(response.context["reservas_confirmadas_hoy_total"], 1)
        self.assertEqual(response.context["reservas_canceladas_hoy_total"], 1)
        self.assertContains(response, pendiente.mascota.nombre)
        self.assertNotContains(response, "Toby")

    def test_reserva_list_muestra_boton_iniciar_atencion(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(9, 0),
            hora_fin=time(9, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.get(reverse("reserva_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("registrar_atencion", args=[self.cliente.id]))
        self.assertContains(response, f"?reserva={obj.id}")

    def test_registrar_atencion_desde_reserva_preselecciona_mascota(self):
        obj = reserva.objects.create(
            mascota=self.mascota,
            evento=self.evento,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            hora_inicio=time(9, 0),
            hora_fin=time(9, 30),
            email_contacto="ana@example.com",
        )

        response = self.client.get(reverse("registrar_atencion", args=[self.cliente.id]) + f"?reserva={obj.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reserva_origen"], obj)
        self.assertEqual(response.context["a_form"].initial["mascota"], self.mascota.id)
        self.assertTrue(response.context["a_form"].fields["mascota"].disabled)
        self.assertContains(response, "Iniciando atención desde la reserva")

    def test_registrar_atencion_desde_reserva_de_otra_veterinaria_devuelve_404(self):
        otra_veterinaria = veterinaria.objects.create(
            nombre="Vet Alterna",
            correo="alterna@example.com",
            smtp_host="",
            smtp_port=587,
            smtp_usuario="",
            smtp_password="",
        )
        otra_especie = especie.objects.create(nombre="Felino", veterinaria=otra_veterinaria)
        otra_raza = raza.objects.create(nombre="Mestizo", especie=otra_especie)
        otra_cliente = cliente.objects.create(
            veterinaria=otra_veterinaria,
            rut=f"11111111-{rut_dv('11111111')}",
            nombre="Cliente Alterno",
            email="alterno@example.com",
            telefono="777777777",
            direccion="Calle Alterna 123",
            comuna=self.comuna,
            estado=self.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )
        otra_mascota = mascota.objects.create(cliente=otra_cliente, raza=otra_raza, nombre="Mishi")
        otra_evento = agendaevento.objects.create(nombre="Consulta general", veterinaria=otra_veterinaria)
        otra_reserva = reserva.objects.create(
            mascota=otra_mascota,
            evento=otra_evento,
            veterinaria=otra_veterinaria,
            fecha=self.manana,
            hora_inicio=time(9, 0),
            hora_fin=time(9, 30),
            email_contacto="alterno@example.com",
        )

        response = self.client.get(reverse("registrar_atencion", args=[self.cliente.id]) + f"?reserva={otra_reserva.id}")

        self.assertEqual(response.status_code, 404)


class CitaGestionTests(ReservaBaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = get_user_model().objects.create_user(
            username="tester_cita",
            password="secret123",
        )
        cls.estado_cita = estadocita.objects.create(nombre="Pendiente")
        cls.control = control.objects.create(nombre="Control general", veterinaria=cls.veterinaria)

    def setUp(self):
        self.client.force_login(self.user)

    def test_gestion_cita_actualiza_estado(self):
        obj = cita.objects.create(
            mascota=self.mascota,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            control=self.control,
            observacion="",
            estado=self.estado_cita,
        )

        response = self.client.post(reverse("cita_estado_update", args=[self.cliente.id, obj.id]), {
            "estado": self.estado_cita.id,
        })

        obj.refresh_from_db()
        self.assertRedirects(response, reverse("citas_por_cliente", args=[self.cliente.id]))
        self.assertEqual(obj.estado_id, self.estado_cita.id)

    def test_regresion_guardado_estado_cita_no_falla(self):
        obj = cita.objects.create(
            mascota=self.mascota,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            control=self.control,
            observacion="",
            estado=self.estado_cita,
        )

        response = self.client.post(reverse("cita_estado_update", args=[self.cliente.id, obj.id]), {
            "estado": self.estado_cita.id,
        })

        obj.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.estado_id, self.estado_cita.id)

    def test_formulario_gestion_cita_renderiza(self):
        obj = cita.objects.create(
            mascota=self.mascota,
            veterinaria=self.veterinaria,
            fecha=self.manana,
            control=self.control,
            observacion="",
            estado=self.estado_cita,
        )

        response = self.client.get(reverse("cita_estado_update", args=[self.cliente.id, obj.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cambiar Estado de Cita")
        self.assertContains(response, "form")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PromocionTests(ReservaBaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = get_user_model().objects.create_user(
            username="tester_promo",
            password="secret123",
        )
        cls.veterinaria = veterinaria.objects.create(
            nombre="Vetnex",
            correo="contacto@vetnex.cl",
            smtp_host="smtp.vetnex.cl",
            smtp_port=587,
            smtp_usuario="contacto@vetnex.cl",
            smtp_password="secret",
        )
        cls.otra_veterinaria = veterinaria.objects.create(
            nombre="OtraVet Promo",
            correo="otrapromo@vet.local",
            smtp_host="smtp.otrapromo.local",
            smtp_port=587,
            smtp_usuario="otrapromo@vet.local",
            smtp_password="secret",
        )
        cls.grupo_admin, _ = Group.objects.get_or_create(name="Administrador")
        cls.admin_user = get_user_model().objects.create_user(
            username="tester_admin",
            password="secret123",
        )
        cls.admin_user.groups.add(cls.grupo_admin)
        cls.admin_user.veterinaria_profile.default_veterinaria = cls.veterinaria
        cls.admin_user.veterinaria_profile.save(update_fields=["default_veterinaria"])
        cls.especie_promo = especie.objects.create(nombre="Canino Promo", veterinaria=cls.veterinaria)
        cls.raza_promo = raza.objects.create(nombre="Mestizo Promo", especie=cls.especie_promo)
        cls.cliente_promo = cliente.objects.create(
            veterinaria=cls.veterinaria,
            rut=f"23456789-{rut_dv('23456789')}",
            nombre="Cliente Promo",
            email="promo@example.com",
            telefono="777777777",
            direccion="Promo 123",
            comuna=cls.comuna,
            estado=cls.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )
        cls.mascota_promo = mascota.objects.create(
            cliente=cls.cliente_promo,
            raza=cls.raza_promo,
            nombre="Rex Promo",
        )
        cls.user.veterinaria_profile.default_veterinaria = cls.veterinaria
        cls.user.veterinaria_profile.save(update_fields=["default_veterinaria"])

    def setUp(self):
        self.client.force_login(self.user)

    def test_listado_promociones_renderiza(self):
        promocion.objects.create(
            veterinaria=self.veterinaria,
            titulo="Promo vacuna",
            descripcion="Descuento vacuna",
            texto_correo="Agenda tu hora",
        )

        response = self.client.get(reverse("promocion_list"), {"q": "vacuna"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Promo vacuna")
        self.assertContains(response, "Enviar Correo")

    def test_crea_promocion_desde_popup(self):
        response = self.client.post(reverse("promocion_create"), {
            "titulo": "Promo dental",
            "descripcion": "Limpieza dental",
            "texto_correo": "Promocion dental para clientes",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(promocion.objects.filter(titulo="Promo dental", veterinaria=self.veterinaria).exists())

    def test_envia_correo_promocion_a_clientes_con_email(self):
        obj = promocion.objects.create(
            veterinaria=self.veterinaria,
            titulo="Promo peluqueria",
            descripcion="",
            texto_correo="Bano y corte promocional",
        )

        response = self.client.post(reverse("promocion_enviar_correo", args=[obj.id]))

        self.assertRedirects(response, reverse("promocion_list"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Promo peluqueria")
        self.assertEqual(mail.outbox[0].from_email, "contacto@vetnex.cl")
        self.assertIn(self.cliente_promo.email, mail.outbox[0].to)

    def test_envia_correo_prueba_promocion(self):
        obj = promocion.objects.create(
            veterinaria=self.veterinaria,
            titulo="Promo test",
            descripcion="",
            texto_correo="Correo de prueba",
        )

        response = self.client.post(reverse("promocion_enviar_prueba", args=[obj.id]), {
            "correo_prueba": "prueba@example.com",
        })

        self.veterinaria.refresh_from_db()
        self.assertRedirects(response, reverse("promocion_list"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prueba@example.com"])
        self.assertEqual(self.veterinaria.correo_prueba, "prueba@example.com")

    def test_usuario_normal_no_accede_a_veterinaria(self):
        response = self.client.get(reverse("veterinaria_update", args=[self.veterinaria.id]))

        self.assertEqual(response.status_code, 403)

    def test_administrador_accede_a_veterinaria_y_ve_menu(self):
        self.veterinaria.logo = "https://cdn.example.com/vetnex-logo.svg"
        self.veterinaria.save(update_fields=["logo"])
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("veterinaria_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veterinarias")
        self.assertNotContains(response, "Veterinaria activa")
        self.assertContains(response, "https://cdn.example.com/vetnex-logo.svg")

        response = self.client.get(reverse("veterinaria_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.veterinaria.nombre)
        self.assertNotContains(response, self.otra_veterinaria.nombre)
        self.assertNotContains(response, "Nueva Veterinaria")
        self.assertEqual(list(response.context["items"]), [self.veterinaria])

        response = self.client.get(reverse("veterinaria_update", args=[self.veterinaria.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar Veterinaria")
        self.assertEqual(self.client.get(reverse("veterinaria_update", args=[self.otra_veterinaria.id])).status_code, 403)


class TenantIsolationTests(ReservaBaseMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.otra_veterinaria = veterinaria.objects.create(
            nombre="OtraVet",
            correo="otra@vet.local",
            smtp_host="smtp.otravet.local",
            smtp_port=587,
            smtp_usuario="otra@vet.local",
            smtp_password="secret",
        )
        cls.superuser = get_user_model().objects.create_superuser(
            username="super_tenant",
            email="super@example.com",
            password="secret123",
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_cliente_puede_repetir_rut_en_otra_veterinaria(self):
        cliente_otra = cliente.objects.create(
            veterinaria=self.otra_veterinaria,
            rut=self.cliente.rut,
            nombre="Cliente Otra Vet",
            email="otra@vet.local",
            telefono="666666666",
            direccion="Otra direccion 999",
            comuna=self.comuna,
            estado=self.estado_cliente,
            origen=OrigenCliente.SISTEMA,
        )

        self.assertEqual(cliente.objects.filter(rut=self.cliente.rut).count(), 2)
        self.assertEqual(cliente_otra.veterinaria_id, self.otra_veterinaria.id)

    def test_superuser_cambia_veterinaria_activa_y_persiste(self):
        response = self.client.post(reverse("veterinaria_set_active"), {
            "veterinaria_id": self.otra_veterinaria.id,
            "next": reverse("veterinaria_list"),
        })

        self.superuser.veterinaria_profile.refresh_from_db()

        self.assertRedirects(response, reverse("veterinaria_list"))
        self.assertEqual(self.client.session.get("active_veterinaria_id"), self.otra_veterinaria.id)
        self.assertEqual(self.superuser.veterinaria_profile.default_veterinaria_id, self.otra_veterinaria.id)

    def test_superuser_ve_selector_y_logo_de_veterinaria_activa(self):
        self.veterinaria.logo = "https://cdn.example.com/master-logo.png"
        self.veterinaria.save(update_fields=["logo"])

        response = self.client.get(reverse("veterinaria_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Datos Veterinaria")
        self.assertContains(response, "Veterinaria activa")
        self.assertContains(response, "https://cdn.example.com/master-logo.png")
        self.assertContains(response, "Nueva Veterinaria")
        self.assertContains(response, "Eliminar")
        self.assertContains(response, str(self.veterinaria.reserva_publica_token))
        self.assertNotContains(response, f"/reservas/publica/{self.veterinaria.id}/")
        self.assertContains(response, "Copiar link")
        self.assertContains(response, "QR")
        self.assertContains(response, "publicQrModal")
        self.assertContains(response, "/qr.svg")

    def test_qr_publico_se_genera_en_svg(self):
        response = self.client.get(reverse("reserva_publica_qr", args=[self.veterinaria.reserva_publica_token]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("image/svg+xml"))
        self.assertContains(response, "<svg", html=False)

    def test_superuser_puede_eliminar_veterinaria_sin_dependencias(self):
        response = self.client.post(reverse("veterinaria_delete", args=[self.otra_veterinaria.id]))

        self.assertRedirects(response, reverse("veterinaria_list"))
        self.assertFalse(veterinaria.objects.filter(id=self.otra_veterinaria.id).exists())
