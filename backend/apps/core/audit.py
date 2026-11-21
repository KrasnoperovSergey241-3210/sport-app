from django.conf import settings

from .models import AuditLog


def client_ip(request):
    if settings.TRUST_PROXY:
        fwd = request.META.get("HTTP_X_FORWARDED_FOR")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def audit(request, action, object_type="", object_id="", actor=None, **details):
    """Записать событие в журнал. Никаких ФИО/контактов/медицинских значений в details не писать!"""
    user = actor or getattr(request, "user", None)
    code = role = None
    if user is not None and getattr(user, "is_authenticated", False):
        code, role = user.code, user.role
    AuditLog.objects.create(
        actor_code=code,
        actor_role=role or "",
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id else "",
        ip=client_ip(request),
        details=details,
    )
