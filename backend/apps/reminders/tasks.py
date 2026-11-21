from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.core.settings_service import get_active_settings

from .models import ReminderSchedule
from .push import send_push
from .services import notify_moment


@shared_task
def send_due_reminders():
    cfg = get_active_settings().data
    offsets = cfg["reminders"]["offsets_days"]
    texts = cfg["texts"]
    sent = 0
    with transaction.atomic():
        due = (
            ReminderSchedule.objects.select_for_update(skip_locked=True)
            .select_related("user")
            .filter(next_notify_at__lte=timezone.now(), stage__lt=len(offsets))[:500]
        )
        for sch in due:
            tokens = list(sch.user.devices.values_list("token", flat=True))
            send_push(tokens, texts["push_title"], texts["push_body"])
            sch.stage += 1
            sch.next_notify_at = notify_moment(sch, offsets, sch.stage)
            sch.save(update_fields=["stage", "next_notify_at"])
            sent += 1
    return sent


@shared_task
def purge_expired():
    from datetime import timedelta

    from apps.assessments.models import AssessmentDraft
    from apps.pii.models import OneTimeCode

    now = timezone.now()
    AssessmentDraft.objects.filter(expires_at__lte=now).delete()
    OneTimeCode.objects.filter(expires_at__lte=now - timedelta(days=1)).delete()
