import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models


class ImmutableMixin(models.Model):
    """Завершённую запись изменить нельзя (ТЗ п. 5.4): повторное save() запрещено."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("Завершённую запись изменить нельзя")
        super().save(*args, **kwargs)


class SettingsVersion(models.Model):
    """Версия серверных настроек (пороги, сроки, тексты). Содержимое версии не редактируется."""

    version = models.PositiveIntegerField("Номер версии", unique=True, editable=False)
    created_at = models.DateTimeField("Дата", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Кто изменил"
    )
    approved_by = models.CharField("Согласовано с постановщиком (кто/когда)", max_length=200, blank=True)
    comment = models.CharField("Комментарий", max_length=300, blank=True)
    data = models.JSONField("Настройки (JSON)")
    is_active = models.BooleanField("Действующая", default=False)

    class Meta:
        ordering = ["-version"]
        verbose_name = "версия настроек"
        verbose_name_plural = "версии настроек"

    def __str__(self):
        return f"Версия {self.version}" + (" (действующая)" if self.is_active else "")


class AuditLog(ImmutableMixin):
    """Журнал входов и обращений к данным. Ссылается на пользователя только по внутреннему коду."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_code = models.UUIDField(null=True, blank=True, db_index=True)
    actor_role = models.CharField(max_length=16, blank=True)
    action = models.CharField(max_length=40, db_index=True)
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-ts"]
        verbose_name = "запись журнала"
        verbose_name_plural = "журнал обращений"


def new_uuid():
    return uuid.uuid4()
