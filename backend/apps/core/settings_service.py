import copy

from django.db import transaction

from .default_settings import DEFAULT_SETTINGS
from .models import SettingsVersion


def get_active_settings() -> SettingsVersion:
    """Действующая версия настроек; при первом обращении создаётся версия 1 из значений по умолчанию."""
    obj = SettingsVersion.objects.filter(is_active=True).order_by("-version").first()
    if obj:
        return obj
    with transaction.atomic():
        obj = SettingsVersion.objects.filter(is_active=True).order_by("-version").first()
        if obj:
            return obj
        last = SettingsVersion.objects.order_by("-version").first()
        return SettingsVersion.objects.create(
            version=(last.version + 1) if last else 1,
            data=copy.deepcopy(DEFAULT_SETTINGS),
            is_active=True,
            comment="Начальная версия",
        )


def validate_settings(data: dict):
    """Проверка структуры JSON настроек (ошибка -> ValueError)."""
    if not isinstance(data, dict):
        raise ValueError("Настройки должны быть JSON-объектом")
    for section in DEFAULT_SETTINGS:
        if section not in data:
            raise ValueError(f"Нет раздела «{section}»")
    for key, default in DEFAULT_SETTINGS["thresholds"].items():
        if not isinstance(data["thresholds"].get(key), (int, float)):
            raise ValueError(f"thresholds.{key} должен быть числом")
    rem = data["reminders"]
    if not isinstance(rem.get("normal_days"), int) or not isinstance(rem.get("flag_days"), int):
        raise ValueError("reminders.normal_days и reminders.flag_days — целые числа")
    offs = rem.get("offsets_days")
    if not (isinstance(offs, list) and offs and all(isinstance(x, int) and x >= 0 for x in offs)):
        raise ValueError("reminders.offsets_days — непустой список целых чисел ≥ 0")
    if not isinstance(data["drafts"].get("ttl_hours"), int):
        raise ValueError("drafts.ttl_hours — целое число")
    for key in DEFAULT_SETTINGS["texts"]:
        if key not in data["texts"]:
            raise ValueError(f"Нет текста texts.{key}")
    for key in DEFAULT_SETTINGS["texts"]["reasons"]:
        if key not in data["texts"]["reasons"]:
            raise ValueError(f"Нет текста texts.reasons.{key}")
