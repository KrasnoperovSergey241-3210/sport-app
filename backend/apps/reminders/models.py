from datetime import time

from django.conf import settings
from django.db import models


class ReminderSchedule(models.Model):
    """Расписание напоминаний пользователя. В день срока, затем на следующий день и через 3 дня (настраивается)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder")
    notify_time = models.TimeField(default=time(9, 0))
    timezone = models.CharField(max_length=64, default="Europe/Moscow")
    due_date = models.DateField(null=True, blank=True)
    stage = models.PositiveSmallIntegerField(default=0)  # сколько напоминаний уже отправлено
    next_notify_at = models.DateTimeField(null=True, blank=True, db_index=True)


class DeviceToken(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios"
        ANDROID = "android"
        WEB = "web"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=8, choices=Platform.choices)
    created_at = models.DateTimeField(auto_now_add=True)
