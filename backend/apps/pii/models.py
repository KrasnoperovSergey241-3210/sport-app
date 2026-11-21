"""Персональные данные — ОТДЕЛЬНАЯ БД (`pii`). Связь с медицинскими данными только через `code`."""
from django.db import models


class Identity(models.Model):
    code = models.UUIDField(primary_key=True)  # = accounts.User.code (внешнего ключа нет: другая БД)
    last_name = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(null=True, blank=True, unique=True)  # хранится в нижнем регистре
    phone = models.CharField(max_length=16, null=True, blank=True, unique=True)  # формат +79991234567
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pii_identity"


class OneTimeCode(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register"
        LOGIN = "login"
        RESET = "reset"

    contact = models.CharField(max_length=254, db_index=True)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pii_one_time_code"
