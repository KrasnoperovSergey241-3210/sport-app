from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.pii.models import Identity

from .models import AthleteProfile, ProfileChange

TRACKED = ("sport", "trainings_per_week", "hours_per_week", "season_period")


def _display(profile: AthleteProfile, field: str) -> str:
    if field == "sport":
        return profile.sport_name()
    v = getattr(profile, field)
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    return str(v)


@transaction.atomic
def apply_profile_update(user, values: dict, changed_at=None) -> AthleteProfile:
    """Обновить профиль и записать изменения отслеживаемых полей в историю."""
    profile = AthleteProfile.objects.select_for_update(of=("self",)).select_related("sport").get(user=user)
    before = {f: _display(profile, f) for f in TRACKED}
    for key, val in values.items():
        setattr(profile, key, val)
    profile.save()
    profile = AthleteProfile.objects.select_related("sport").get(pk=profile.pk)
    when = changed_at or timezone.now()
    for f in TRACKED:
        after = _display(profile, f)
        if after != before[f]:
            ProfileChange.objects.create(user=user, field=f, old_value=before[f], new_value=after, changed_at=when)
    return profile


def get_names(user) -> dict:
    ident = Identity.objects.filter(code=user.code).first()
    if not ident:
        return {"last_name": "", "first_name": "", "middle_name": ""}
    return {"last_name": ident.last_name, "first_name": ident.first_name, "middle_name": ident.middle_name}


def set_names(user, values: dict):
    allowed = {k: v for k, v in values.items() if k in ("last_name", "first_name", "middle_name")}
    if allowed:
        Identity.objects.filter(code=user.code).update(**allowed)
