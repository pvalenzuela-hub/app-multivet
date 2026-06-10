# app-multivet

## Arranque local

1. Crear y activar un entorno virtual.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Ejecutar `python manage.py migrate`.
4. Crear un superusuario con `python manage.py createsuperuser`.
5. Levantar el servidor con `python manage.py runserver`.

## Configuracion

- El proyecto carga variables desde `.env`.
- Si no defines `DATABASE_URL`, usa SQLite en `db.sqlite3`.
- La migracion `0022_seed_estado_basico` crea los estados base necesarios para `cliente` y `cita`.
- La migracion `0023_seed_demo_data` carga una veterinaria y datos demo minimos para probar la app.
- La migracion `0024_usuario_veterinaria_y_tenant_nullable` crea el perfil por usuario y agrega los FKs tenantizados.
- La migracion `0025_backfill_tenant_data` asigna los registros existentes a la veterinaria master.
- La migracion `0026_tenant_constraints` deja los campos obligatorios y aplica unicidad por veterinaria.
- Los catálogos globales `Estados Cliente` y `Estados Cita` se administran desde la app solo para superuser.
- El superuser puede cambiar la veterinaria activa desde el selector del sidebar y ese cambio se persiste como default.
- Los flujos publicos de reserva siguen anclados a la veterinaria master; quedan fuera de esta ola.
- Para una base de produccion usa `python manage.py seed_production` despues de `migrate`; acepta `--logo-url`, `--nombre` y credenciales SMTP para dejar la veterinaria base lista sin los datos demo.
- Si no pasas `--logo-url`, el comando usa `SEED_VETERINARIA_LOGO_URL`, `PUBLIC_SITE_URL` o un logo placeholder seguro.

## Nota

- Para enviar correos reales, el `.env` debe usar backend SMTP.
- Los usuarios normales quedan asociados a una sola veterinaria.
