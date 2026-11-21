from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import ReminderSchedule


def tz_of(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def get_schedule(user) -> ReminderSchedule:
    return ReminderSchedule.objects.get_or_create(user=user)[0]


def notify_moment(sch: ReminderSchedule, offsets, stage):
    """Момент отправки напоминания №stage (None, если все отправлены)."""
    if sch.due_date is None or stage >= len(offsets):
        return None
    day = sch.due_date + timedelta(days=offsets[stage])
    return datetime.combine(day, sch.notify_time, tzinfo=tz_of(sch.timezone))


def schedule_next(user, due_date, cfg):
    """Любая новая самооценка пересчитывает срок (сценарий 16)."""
    sch = get_schedule(user)
    sch.due_date = due_date
    sch.stage = 0
    sch.next_notify_at = notify_moment(sch, cfg["reminders"]["offsets_days"], 0)
    sch.save()
    return sch


def reschedule_current(sch: ReminderSchedule, cfg):
    """После смены времени/часового пояса пересчитать ближайшее напоминание."""
    sch.next_notify_at = notify_moment(sch, cfg["reminders"]["offsets_days"], sch.stage)
    sch.save()
