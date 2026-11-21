from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.utils import age_on


class Sport(models.Model):
    """Справочник видов спорта (Приложение В). Пользователю показывается только название."""

    ext_no = models.PositiveIntegerField("№ в файле", unique=True, null=True, blank=True)
    name = models.CharField("Вид спорта", max_length=300, db_index=True)
    type_esc = models.CharField("Тип (ESC 2020)", max_length=50, blank=True)
    intensity_esc = models.CharField("Интенсивность (ESC 2020)", max_length=50, blank=True)
    static_mitchell = models.CharField("Статический компонент (Митчелл)", max_length=50, blank=True)
    dynamic_mitchell = models.CharField("Динамический компонент (Митчелл)", max_length=50, blank=True)
    is_active = models.BooleanField("Показывать в списке", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "вид спорта"
        verbose_name_plural = "виды спорта"

    def __str__(self):
        return self.name

    def snapshot(self) -> dict:
        return {
            "id": self.pk,
            "name": self.name,
            "custom": False,
            "type_esc": self.type_esc,
            "intensity_esc": self.intensity_esc,
            "static_mitchell": self.static_mitchell,
            "dynamic_mitchell": self.dynamic_mitchell,
        }


class AthleteProfile(models.Model):
    class Sex(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"

    class Season(models.TextChoices):
        REST = "rest", "Отдых"
        PREPARATION = "preparation", "Подготовка к сезону"
        CAMP = "camp", "Сборы"
        COMPETITION = "competition", "Период соревнований"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    sex = models.CharField(max_length=8, choices=Sex.choices, blank=True)
    birth_date = models.DateField()
    sport = models.ForeignKey(Sport, null=True, blank=True, on_delete=models.PROTECT)
    sport_custom = models.CharField(max_length=200, blank=True)  # вариант «Другой»
    start_age_any = models.PositiveSmallIntegerField(null=True, blank=True)
    start_age_sport = models.PositiveSmallIntegerField(null=True, blank=True)
    trainings_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    season_period = models.CharField(max_length=16, choices=Season.choices, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def age(self, on=None) -> int:
        return age_on(self.birth_date, on or timezone.localdate())

    @property
    def is_complete(self) -> bool:
        return bool(
            self.sex
            and (self.sport_id or self.sport_custom)
            and self.start_age_any is not None
            and self.start_age_sport is not None
            and self.trainings_per_week is not None
            and self.hours_per_week is not None
        )

    def sport_name(self) -> str:
        return self.sport.name if self.sport_id else self.sport_custom

    def sport_snapshot(self) -> dict:
        if self.sport_id:
            return self.sport.snapshot()
        return {"id": None, "name": self.sport_custom, "custom": True, "type_esc": "", "intensity_esc": "",
                "static_mitchell": "", "dynamic_mitchell": ""}


class ProfileChange(models.Model):
    """История изменений профиля: вид спорта, тренировки, часы, период сезона (ТЗ п. 5.2, 5.6)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_changes")
    field = models.CharField(max_length=32)
    old_value = models.CharField(max_length=300, blank=True)
    new_value = models.CharField(max_length=300, blank=True)
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
