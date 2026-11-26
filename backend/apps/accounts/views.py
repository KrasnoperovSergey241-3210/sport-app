from datetime import date

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.audit import audit
from apps.core.errors import DomainError
from apps.core.permissions import IsAthlete
from apps.core.settings_service import get_active_settings
from apps.core.utils import age_on

from . import services as svc
from .serializers import (
    ContactSerializer,
    LoginSerializer,
    OtpVerifySerializer,
    PasswordSerializer,
    RegisterSerializer,
    RegisterStartSerializer,
    RegisterVerifySerializer,
    ResetConfirmSerializer,
)

BAD_LOGIN = "Неверный логин или пароль"


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        return JWTAuthentication().authenticate_header(request)


class OtpMixin:
    def otp_response(self, code=None):
        data = {"detail": "Если данные верны, код отправлен", "resend_in": settings.OTP_RESEND_SECONDS}
        if code and settings.DEV_ECHO_OTP:  # только для разработки
            data["debug_code"] = code
        return Response(data)


def _check_registration_age(birth):
    if age_on(birth, timezone.localdate()) < 18:
        raise DomainError(get_active_settings().data["texts"]["age_restriction"], "age_restriction")


def _registration_response(request, user):
    audit(request, "register", "user", user.code, actor=user)
    return Response(svc.tokens_for(user), status=status.HTTP_201_CREATED)


class RegisterView(PublicView):
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _check_registration_age(data["birth_date"])
        user = svc.register_athlete("email", data["email"].lower(), data["password"], data["birth_date"])
        return _registration_response(request, user)


class RegisterStartView(OtpMixin, PublicView):
    """Шаг 1 регистрации: контакт + дата рождения + согласие -> одноразовый код."""

    throttle_scope = "otp"

    def post(self, request):
        s = RegisterStartSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        birth = s.validated_data["birth_date"]
        _check_registration_age(birth)
        code = None
        ident = svc.find_identity(kind, contact)
        if not ident or not svc.User.objects.filter(code=ident.code).exists():
            code = svc.issue_otp(kind, contact, "register", {"birth_date": birth.isoformat()})
        # если контакт уже зарегистрирован — отвечаем так же (не раскрываем наличие аккаунта)
        return self.otp_response(code)


class RegisterVerifyView(PublicView):
    """Шаг 2: код + пароль -> учётная запись (без ПДн), согласие, профиль, токены."""

    throttle_scope = "auth"

    def post(self, request):
        s = RegisterVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        otp = svc.verify_otp(contact, "register", s.validated_data["code"])
        birth = date.fromisoformat(otp.payload["birth_date"])
        _check_registration_age(birth)
        try:
            user = svc.register_athlete(kind, contact, s.validated_data["password"], birth)
        except Exception:
            raise ValidationError({"contact": ["Не удалось завершить регистрацию"]})
        return _registration_response(request, user)


class LoginView(PublicView):
    throttle_scope = "auth"

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            kind, contact = svc.normalize_contact(s.validated_data["contact"])
        except ValidationError:
            raise AuthenticationFailed(BAD_LOGIN)
        user = svc.find_user(kind, contact)
        if not user:
            audit(request, "login_failed", "user")
            raise AuthenticationFailed(BAD_LOGIN)
        svc.ensure_not_locked(user)
        if not user.check_password(s.validated_data["password"]):
            svc.register_failure(user)
            audit(request, "login_failed", "user", user.code, actor=user)
            raise AuthenticationFailed(BAD_LOGIN)
        svc.register_success(user)
        audit(request, "login", "user", user.code, actor=user, method="password")
        return Response(svc.tokens_for(user))


class LoginOtpStartView(OtpMixin, PublicView):
    throttle_scope = "otp"

    def post(self, request):
        s = ContactSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        code = None
        if svc.find_user(kind, contact):
            code = svc.issue_otp(kind, contact, "login")
        return self.otp_response(code)


class LoginOtpVerifyView(PublicView):
    throttle_scope = "auth"

    def post(self, request):
        s = OtpVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        svc.verify_otp(contact, "login", s.validated_data["code"])
        user = svc.find_user(kind, contact)
        if not user:
            raise AuthenticationFailed(BAD_LOGIN)
        svc.ensure_not_locked(user)
        audit(request, "login", "user", user.code, actor=user, method="otp")
        return Response(svc.tokens_for(user))


class PasswordResetStartView(OtpMixin, PublicView):
    throttle_scope = "otp"

    def post(self, request):
        s = ContactSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        code = None
        if svc.find_user(kind, contact):
            code = svc.issue_otp(kind, contact, "reset")
        return self.otp_response(code)


class PasswordResetConfirmView(PublicView):
    throttle_scope = "auth"

    def post(self, request):
        s = ResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind, contact = svc.normalize_contact(s.validated_data["contact"])
        svc.verify_otp(contact, "reset", s.validated_data["code"])
        user = svc.find_user(kind, contact)
        if not user:
            raise ValidationError({"code": ["Неверный или просроченный код"]})
        try:
            validate_password(s.validated_data["new_password"], user)
        except Exception as e:
            raise ValidationError({"new_password": list(getattr(e, "messages", [str(e)]))})
        user.set_password(s.validated_data["new_password"])
        user.failed_attempts, user.locked_until = 0, None
        user.save()
        svc.revoke_all_tokens(user)
        audit(request, "password_reset", "user", user.code, actor=user)
        return Response({"detail": "Пароль изменён"})


class RefreshView(TokenRefreshView):
    throttle_scope = "auth"


class LogoutView(APIView):
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass
        audit(request, "logout", "user", request.user.code)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountView(APIView):
    """GET — краткие сведения об аккаунте; DELETE — удаление аккаунта (ТЗ п. 5.1, сценарий 19)."""

    permission_classes = [IsAthlete]
    audit_action = "account_deleted"

    def get(self, request):
        c = request.user.consents.order_by("-given_at").first()
        return Response(
            {
                "user_code": str(request.user.code),
                "consent_given_at": c.given_at if c else None,
                "policy_version": c.policy_version if c else None,
            }
        )

    def delete(self, request):
        s = PasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not request.user.check_password(s.validated_data["password"]):
            raise DomainError("Неверный пароль", "bad_password", 403)
        audit(request, self.audit_action, "user", request.user.code)  # в журнале остаётся только код
        svc.delete_account(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevokeConsentView(AccountView):
    """Отзыв согласия = удаление данных (ТЗ, раздел 7)."""

    audit_action = "consent_revoked"

    def post(self, request):
        return self.delete(request)
