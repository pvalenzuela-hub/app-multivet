# urls.py ultima version 21:23
from django.urls import path
from .views import (
    AppLoginView, AppLogoutView,
    cliente_list, cliente_create, cliente_update,
    mascota_update,
    registrar_atencion, atenciones_por_cliente, citas_por_cliente,
    ficha_clinica_buscar, atencion_detalle_view, mascotas_por_cliente,
    ficha_clinica_mascota, mascota_create_cliente, cita_create_cliente,
    cita_estado_update,
    especie_list, especie_create, especie_delete, especie_update,
    raza_list, raza_delete, raza_create, raza_update,
    prestacion_list, prestacion_create, prestacion_delete, prestacion_update,
    control_list, control_create, control_delete, control_update, cliente_detail,
    estadocliente_list, estadocliente_create, estadocliente_update, estadocliente_delete,
    estadocita_list, estadocita_create, estadocita_update, estadocita_delete,
    cita_delete, atencion_delete, mascota_delete_confirm, cliente_delete_confirm,
    dashboard_panel, atencion_update, atenciondetalle_update, atenciondetalle_delete,
    cita_update_global, cita_delete_global, citas_pendientes_filtrado,
    cita_check_global, agendaevento_list, agendaevento_create, agendaevento_update,
    agendaevento_delete, agendaeventohorario_list, agendaeventohorario_create,
    agendaeventohorario_update, agendaeventohorario_delete, agendabloqueo_list,
    agendabloqueo_create, agendabloqueo_update, agendabloqueo_delete,
    reserva_list, reserva_update_estado, reserva_publica_acceso,
    reserva_publica_cambiar_cliente, reserva_publica_nueva, reserva_publica_slots,
    reserva_publica_registro,
    reserva_publica_confirmacion,
    promocion_list, promocion_create, promocion_update, promocion_detail,
    promocion_delete, promocion_enviar_correo, promocion_enviar_prueba, veterinaria_update,
    veterinaria_list, veterinaria_create, veterinaria_delete, veterinaria_set_active,
)

urlpatterns = [
    path("login/", AppLoginView.as_view(), name="login"),
    path("logout/", AppLogoutView.as_view(), name="logout"),
    path("reservas/publica/", reserva_publica_acceso, name="reserva_publica_acceso"),
    path("reservas/publica/registro/", reserva_publica_registro, name="reserva_publica_registro"),
    path("reservas/publica/cambiar-cliente/", reserva_publica_cambiar_cliente, name="reserva_publica_cambiar_cliente"),
    path("reservas/publica/nueva/", reserva_publica_nueva, name="reserva_publica_nueva"),
    path("reservas/publica/horarios/", reserva_publica_slots, name="reserva_publica_slots"),
    path("reservas/publica/confirmacion/<int:reserva_id>/", reserva_publica_confirmacion, name="reserva_publica_confirmacion"),

    path("", cliente_list, name="cliente_list"),
    path("clientes/nuevo/", cliente_create, name="cliente_create"),
    path("clientes/<int:pk>/editar/", cliente_update, name="cliente_update"),

    path("mascotas/<int:pk>/editar/", mascota_update, name="mascota_update"),

    path("clientes/<int:cliente_id>/atenciones/", atenciones_por_cliente, name="atenciones_por_cliente"),
    path("clientes/<int:cliente_id>/atenciones/<int:atencion_id>/editar/", atencion_update, name="atencion_update"),

    path("clientes/<int:cliente_id>/citas/", citas_por_cliente, name="citas_por_cliente"),
    path("clientes/<int:cliente_id>/citas/nueva/", cita_create_cliente, name="cita_create_cliente"),
    path("clientes/<int:cliente_id>/registrar-atencion/", registrar_atencion, name="registrar_atencion"),

    path("ficha-clinica/", ficha_clinica_buscar, name="ficha_clinica_buscar"),

    path("atenciones/<int:atencion_id>/detalle/", atencion_detalle_view, name="atencion_detalle"),
    path(
        "clientes/<int:cliente_id>/atenciones/<int:atencion_id>/detalle/<int:detalle_id>/editar/",
        atenciondetalle_update,
        name="atenciondetalle_update"
    ),
    path(
        "clientes/<int:cliente_id>/atenciones/<int:atencion_id>/detalle/<int:detalle_id>/eliminar/",
        atenciondetalle_delete,
        name="atenciondetalle_delete"
    ),

    path("clientes/<int:cliente_id>/mascotas/", mascotas_por_cliente, name="mascotas_por_cliente"),
    path("clientes/<int:cliente_id>/mascotas/nueva/", mascota_create_cliente, name="mascota_create_cliente"),

    path("mascotas/<int:mascota_id>/ficha/", ficha_clinica_mascota, name="ficha_clinica_mascota"),
    path(
        "clientes/<int:cliente_id>/citas/<int:cita_id>/estado/",
        cita_estado_update,
        name="cita_estado_update"
    ),
    path("clientes/<int:cliente_id>/ver/", cliente_detail, name="cliente_detail"),
    path("clientes/<int:cliente_id>/citas/<int:cita_id>/eliminar/", cita_delete, name="cita_delete"),
    path("clientes/<int:cliente_id>/atenciones/<int:atencion_id>/eliminar/", atencion_delete, name="atencion_delete"),

    path("mascota/<int:mascota_id>/eliminar/", mascota_delete_confirm, name="mascota_delete"),
    path("cliente/<int:cliente_id>/eliminar/", cliente_delete_confirm, name="cliente_delete"),


    # Catálogo - Especies
    path("catalogo/especies/", especie_list, name="especie_list"),
    path("catalogo/especies/nueva/", especie_create, name="especie_create"),
    path("catalogo/especies/<int:pk>/editar/", especie_update, name="especie_update"),
    path("catalogo/especies/<int:pk>/eliminar/", especie_delete, name="especie_delete"),

    # Catálogo - Razas
    path("catalogo/razas/", raza_list, name="raza_list"),
    path("catalogo/razas/nueva/", raza_create, name="raza_create"),
    path("catalogo/razas/<int:pk>/editar/", raza_update, name="raza_update"),
    path("catalogo/razas/<int:pk>/eliminar/", raza_delete, name="raza_delete"),

    # Catálogo - Prestaciones
    path("catalogo/prestaciones/", prestacion_list, name="prestacion_list"),
    path("catalogo/prestaciones/nueva/", prestacion_create, name="prestacion_create"),
    path("catalogo/prestaciones/<int:pk>/editar/", prestacion_update, name="prestacion_update"),
    path("catalogo/prestaciones/<int:pk>/eliminar/", prestacion_delete, name="prestacion_delete"),

    # Catálogo - Controles
    path("catalogo/controles/", control_list, name="control_list"),
    path("catalogo/controles/nuevo/", control_create, name="control_create"),
    path("catalogo/controles/<int:pk>/editar/", control_update, name="control_update"),
    path("catalogo/controles/<int:pk>/eliminar/", control_delete, name="control_delete"),

    # Catálogo - Estados
    path("catalogo/estados-clientes/", estadocliente_list, name="estadocliente_list"),
    path("catalogo/estados-clientes/nuevo/", estadocliente_create, name="estadocliente_create"),
    path("catalogo/estados-clientes/<int:pk>/editar/", estadocliente_update, name="estadocliente_update"),
    path("catalogo/estados-clientes/<int:pk>/eliminar/", estadocliente_delete, name="estadocliente_delete"),
    path("catalogo/estados-citas/", estadocita_list, name="estadocita_list"),
    path("catalogo/estados-citas/nuevo/", estadocita_create, name="estadocita_create"),
    path("catalogo/estados-citas/<int:pk>/editar/", estadocita_update, name="estadocita_update"),
    path("catalogo/estados-citas/<int:pk>/eliminar/", estadocita_delete, name="estadocita_delete"),

    path("agenda/eventos/", agendaevento_list, name="agendaevento_list"),
    path("agenda/eventos/nuevo/", agendaevento_create, name="agendaevento_create"),
    path("agenda/eventos/<int:pk>/editar/", agendaevento_update, name="agendaevento_update"),
    path("agenda/eventos/<int:pk>/eliminar/", agendaevento_delete, name="agendaevento_delete"),
    path("agenda/eventos/<int:evento_id>/horarios/", agendaeventohorario_list, name="agendaeventohorario_list"),
    path("agenda/eventos/<int:evento_id>/horarios/nuevo/", agendaeventohorario_create, name="agendaeventohorario_create"),
    path("agenda/eventos/<int:evento_id>/horarios/<int:pk>/editar/", agendaeventohorario_update, name="agendaeventohorario_update"),
    path("agenda/eventos/<int:evento_id>/horarios/<int:pk>/eliminar/", agendaeventohorario_delete, name="agendaeventohorario_delete"),
    path("agenda/bloqueos/", agendabloqueo_list, name="agendabloqueo_list"),
    path("agenda/bloqueos/nuevo/", agendabloqueo_create, name="agendabloqueo_create"),
    path("agenda/bloqueos/<int:pk>/editar/", agendabloqueo_update, name="agendabloqueo_update"),
    path("agenda/bloqueos/<int:pk>/eliminar/", agendabloqueo_delete, name="agendabloqueo_delete"),
    path("reservas/", reserva_list, name="reserva_list"),
    path("reservas/<int:reserva_id>/estado/", reserva_update_estado, name="reserva_update_estado"),
    path("promociones/", promocion_list, name="promocion_list"),
    path("promociones/nueva/", promocion_create, name="promocion_create"),
    path("promociones/<int:pk>/editar/", promocion_update, name="promocion_update"),
    path("promociones/<int:pk>/ver/", promocion_detail, name="promocion_detail"),
    path("promociones/<int:pk>/eliminar/", promocion_delete, name="promocion_delete"),
    path("promociones/<int:pk>/enviar-correo/", promocion_enviar_correo, name="promocion_enviar_correo"),
    path("promociones/<int:pk>/enviar-prueba/", promocion_enviar_prueba, name="promocion_enviar_prueba"),
    path("veterinarias/", veterinaria_list, name="veterinaria_list"),
    path("veterinarias/nueva/", veterinaria_create, name="veterinaria_create"),
    path("veterinarias/<int:pk>/editar/", veterinaria_update, name="veterinaria_update"),
    path("veterinarias/<int:pk>/eliminar/", veterinaria_delete, name="veterinaria_delete"),
    path("veterinarias/activa/", veterinaria_set_active, name="veterinaria_set_active"),

    path("panel/", dashboard_panel, name="dashboard_panel"),

    # Citas - Pendientes
    #path("citas/pendientes/", citas_pendientes_list, name="citas_pendientes_list"),
    path("citas/<int:cita_id>/editar/", cita_update_global, name="cita_update_global"),
    path("citas/<int:cita_id>/eliminar/", cita_delete_global, name="cita_delete_global"),
    path("citas/pendientes-filtrado/", citas_pendientes_filtrado, name="citas_pendientes_filtrado"),
    path("cita/<int:cita_id>/check/", cita_check_global, name="cita_check_global"),

]
