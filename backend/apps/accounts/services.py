import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.errors import DomainError
from apps.pii.models import Identity, OneTimeCode

from .models import Consent, User

log = logging.getLogger(__name__)


# ---------- контакты ----------
def normalize_contact(value: str):
    """-> ("email"|"phone", нормализованное значение)"""
    v = (value or "").strip()
    if "@" in v:
        v = v.lower()
        try:
            validate_email(v)
        except DjangoValidationError:
            raise ValidationError({"contact": ["Некорректный адрес электронной почты"]})
        return "email", v
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if not 11 <= len(digits) <= 15:
        raise ValidationError({"contact": ["Некорректный номер телефона"]})
    return "phone", "+" + digits


def find_identity(kind: str, contact: str):
    return Identity.objects.filter(**{kind: contact}).first()


def find_user(kind: str, contact: str):
    ident = find_identity(kind, contact)
    if not ident:
        return None
    return User.objects.filter(code=ident.code, role=User.Role.ATHLETE, is_active=True).first()


# ---------- одноразовые коды ----------
def _hash(contact, purpose, code):
    msg = f"{purpose}:{contact}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def send_code(kind, contact, code):
    text = f"Ваш код подтверждения: {code}. Никому его не сообщайте."
    if kind == "email":
        send_mail("Код подтверждения", text, settings.DEFAULT_FROM_EMAIL, [contact])
        return
    if settings.SMS_BACKEND == "console":
        if not settings.DEBUG:
            raise ImproperlyConfigured("SMS_BACKEND=console нельзя использовать в продакшене")
        log.warning("[SMS -> %s] %s", contact, text)
        return
    raise NotImplementedError("Подключите SMS-провайдера в apps/accounts/services.py:send_code")


def issue_otp(kind, contact, purpose, payload=None):
    """Создать и отправить код. Не чаще раза в OTP_RESEND_SECONDS. Возвращает код (для DEV_ECHO_OTP)."""
    now = timezone.now()
    last = OneTimeCode.objects.filter(contact=contact, purpose=purpose).order_by("-created_at").first()
    if last:
        wait = settings.OTP_RESEND_SECONDS - (now - last.created_at).total_seconds()
        if wait > 0:
            raise Throttled(wait=int(wait) + 1, detail="Код уже отправлен. Повторите запрос позже")
    OneTimeCode.objects.filter(contact=contact, purpose=purpose, used_at__isnull=True).update(used_at=now)
    code = f"{secrets.randbelow(10**6):06d}"
    OneTimeCode.objects.create(
        contact=contact,
        purpose=purpose,
        code_hash=_hash(contact, purpose, code),
        payload=payload or {},
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    send_code(kind, contact, code)
    return code


def verify_otp(contact, purpose, code) -> OneTimeCode:
    err = ValidationError({"code": ["Неверный или просроченный код"]})
    now = timezone.now()
    with transaction.atomic(using="pii"):
        otp = (
            OneTimeCode.objects.select_for_update()
            .filter(contact=contact, purpose=purpose, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if not otp or otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise err
        otp.attempts += 1
        if not hmac.compare_digest(otp.code_hash, _hash(contact, purpose, str(code))):
            otp.save(update_fields=["attempts"])
            return_err = True
        else:
            otp.used_at = now
            otp.save(update_fields=["attempts", "used_at"])
            return_err = False
    if return_err:
        raise err
    return otp


# ---------- регистрация / удаление ----------
@transaction.atomic(using="pii")
def register_athlete(kind, contact, password, birth_date) -> User:
    from apps.profiles.models import AthleteProfile

    code = uuid.uuid4()
    identity, created = Identity.objects.select_for_update().get_or_create(
        **{kind: contact}, defaults={"code": code}
    )
    # «осиротевшая» запись ПДн (аккаунт уже удалён) не должна блокировать повторную регистрацию
    if not created:
        if User.objects.filter(code=identity.code).exists():
            raise DomainError("Не удалось создать аккаунт. Если вы уже зарегистрированы, войдите в аккаунт.", "contact_in_use", 409)
        identity.delete()
        Identity.objects.create(code=code, **{kind: contact})

    with transaction.atomic():
        user = User.objects.create_user(username=str(code), password=password, code=code, role=User.Role.ATHLETE)
        Consent.objects.create(user=user, policy_version=settings.POLICY_VERSION)
        AthleteProfile.objects.create(user=user, birth_date=birth_date)
    return user


def delete_account(user: User):
    """Полное удаление: медицинские данные (каскадом), затем ПДн и одноразовые коды."""
    code = user.code
    ident = Identity.objects.filter(code=code).first()
    contacts = [c for c in ((ident.email, ident.phone) if ident else ()) if c]
    with transaction.atomic():
        user.delete()
    OneTimeCode.objects.filter(contact__in=contacts).delete()
    Identity.objects.filter(code=code).delete()


# ---------- вход ----------
def tokens_for(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user_code": str(user.code)}


def ensure_not_locked(user: User):
    if user.locked_until and user.locked_until > timezone.now():
        wait = int((user.locked_until - timezone.now()).total_seconds()) + 1
        raise Throttled(wait=wait, detail="Слишком много неверных попыток. Повторите позже")


def register_failure(user: User):
    user.failed_attempts += 1
    if user.failed_attempts >= settings.LOGIN_MAX_FAILED:
        user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        user.failed_attempts = 0
    user.save(update_fields=["failed_attempts", "locked_until"])


def register_success(user: User):
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_attempts", "locked_until"])


def revoke_all_tokens(user: User):
    for t in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=t)
