import uuid

from django.conf import settings
from django.db import models

from apps.core.models import ImmutableMixin, SettingsVersion


class AssessmentDraft(models.Model):
    """Черновик незавершённой самооценки (хранится 72 ч, не попадает в историю)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessment_draft")
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)


class SelfAssessment(ImmutableMixin):
    """Завершённая самооценка. Изменение запрещено (ImmutableMixin): при ошибке — новая самооценка."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessments")
    client_uuid = models.UUIDField()  # ключ идемпотентности (офлайн-синхронизация)
    filled_at = models.DateTimeField(db_index=True)  # дата и время записи
    received_at = models.DateTimeField(auto_now_add=True)

    # данные профиля на дату заполнения
    age = models.PositiveSmallIntegerField()
    sport = models.JSONField()  # название + характеристики из справочника (пользователю не показываются)
    trainings_per_week = models.PositiveSmallIntegerField()
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=1)
    season_period = models.CharField(max_length=16)

    # анкета
    tolerance = models.PositiveSmallIntegerField()  # 2.1
    restq_filled = models.BooleanField(default=False)
    bp_measured = models.BooleanField(default=False)
    sbp = models.PositiveSmallIntegerField(null=True, blank=True)
    dbp = models.PositiveSmallIntegerField(null=True, blank=True)
    pulse = models.PositiveSmallIntegerField(null=True, blank=True)
    kerdo_index = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    kerdo_class = models.CharField(max_length=20, blank=True)
    hrv_has_device = models.BooleanField(default=False)
    hrv_value = models.FloatField(null=True, blank=True)
    hrv_metric = models.CharField(max_length=10, blank=True)
    hrv_device = models.CharField(max_length=100, blank=True)
    hrv_date = models.DateField(null=True, blank=True)
    hrv_conditions = models.CharField(max_length=10, blank=True)
    answers = models.JSONField()  # все исходные ответы и комментарии (без 77 ответов RESTQ)

    # итог
    red_flag = models.BooleanField()
    urgent = models.BooleanField()
    reasons = models.JSONField(default=list)
    next_due_date = models.DateField()
    settings_version = models.ForeignKey(SettingsVersion, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-filled_at"]
        constraints = [models.UniqueConstraint(fields=["user", "client_uuid"], name="uniq_assessment_client_uuid")]
        indexes = [models.Index(fields=["user", "-filled_at"])]


class RestqResult(ImmutableMixin):
    assessment = models.OneToOneField(SelfAssessment, on_delete=models.CASCADE, related_name="restq")
    timing = models.CharField(max_length=6)  # before | after
    answers = models.JSONField()  # {"1": 3, ..., "77": 0} — исходные ответы
    scales = models.JSONField()  # {"1": {"sum": 9, "mean": 2.25}, ... "19": ...}
    blocks = models.JSONField()  # {"OS": .., "OV": .., "SS": .., "SV": ..}
    total_stress = models.FloatField()
    total_recovery = models.FloatField()
    balance = models.FloatField()
