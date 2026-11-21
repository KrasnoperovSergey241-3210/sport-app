import logging

from django.conf import settings

log = logging.getLogger(__name__)


def send_push(tokens, title, body):
    """Текст уведомления не содержит медицинских сведений (ТЗ п. 5.5, раздел 7)."""
    if not tokens:
        return
    if settings.PUSH_BACKEND == "fcm":
        import firebase_admin
        from firebase_admin import messaging

        if not firebase_admin._apps:
            firebase_admin.initialize_app()  # ключ — переменная GOOGLE_APPLICATION_CREDENTIALS
        messaging.send_each_for_multicast(
            messaging.MulticastMessage(tokens=list(tokens), notification=messaging.Notification(title=title, body=body))
        )
    else:
        log.info("[PUSH x%d] %s — %s", len(tokens), title, body)
