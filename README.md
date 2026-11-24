# App-Multivet

Clinica veterinaria multi-tenant construida con Django.

## Stack
- Django 5.2 + PostgreSQL (psycopg3)
- Celery + Redis para tareas en segundo plano
- Gunicorn en produccion
- django-cors-headers, django-ratelimit, django-redis, django-htmlmin
- Multi-tenancy: tenancy por subdominio/cliente (tenancy.py, context_processors)

## Estructura
- appclinica/ - app principal (modelos, vistas, templates, tasks, middleware, signals)
- proveterinaria/ - proyecto Django (settings, urls raiz)
- staticfiles/ - archivos estaticos recolectados
- db.sqlite3 - base local de desarrollo
- manage.py - entry point

## Ejecucion local
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Base de datos
- Produccion: PostgreSQL via dj-database-url (DATABASE_URL)
- Celery: broker Redis (REDIS_URL)

## Git
- Remote: git@github.com:pvalenzuela-hub/app-multivet.git
