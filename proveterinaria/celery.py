import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proveterinaria.settings")

app = Celery("proveterinaria")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
