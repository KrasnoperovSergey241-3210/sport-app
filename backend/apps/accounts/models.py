import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError("username обязателен")
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.update(role=User.Role.ADMIN, is_staff=True, is_superuser=True)
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Учётная запись БЕЗ персональных данных. Спортсмен: username = str(code)."""

    class Role(models.TextChoices):
        ATHLETE = "athlete", "Спортсмен"
        ADMIN = "admin", "Администратор"

    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # внутренний код
    username = models.CharField(max_length=64, unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ATHLETE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "username"

    def __str__(self):
        return self.username


class Consent(models.Model):
    """Согласие на обработку ПДн, включая сведения о здоровье (ТЗ п. 5.1)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents")
    policy_version = models.CharField(max_length=20)
    given_at = models.DateTimeField(default=timezone.now)
