import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("sport")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # напоминания о самооценке (п. 5.5): проверка каждые 5 минут
    "send-due-reminders": {"task": "apps.reminders.tasks.send_due_reminders", "schedule": crontab(minute="*/5")},
    # чистка просроченных черновиков (72 ч) и одноразовых кодов
    "purge-expired": {"task": "apps.reminders.tasks.purge_expired", "schedule": crontab(minute=15)},
}
