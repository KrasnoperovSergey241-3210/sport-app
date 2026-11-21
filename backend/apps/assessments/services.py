from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import DomainError
from apps.core.utils import age_on, jsonable
from apps.profiles.models import AthleteProfile
from apps.profiles.services import apply_profile_update
from apps.reminders.services import get_schedule, schedule_next, tz_of

from .models import AssessmentDraft, RestqResult, SelfAssessment
from .scoring import evaluate, kerdo_class, kerdo_index, next_due_days, restq_score


@transaction.atomic
def complete_assessment(user, data: dict, settings_obj):
    """Сохранить завершённую самооценку. Все расчёты выполняются на сервере по исходным ответам."""
    cfg = settings_obj.data
    answers = jsonable(data["answers"])
    profile = AthleteProfile.objects.select_related("sport").get(user=user)
    if not profile.is_complete:
        raise DomainError("Сначала заполните профиль", "profile_incomplete", 409)

    filled_at = data.get("filled_at") or timezone.now()
    local_date = filled_at.astimezone(tz_of(get_schedule(user).timezone)).date()
    is_latest = not SelfAssessment.objects.filter(user=user, filled_at__gt=filled_at).exists()

    if is_latest:  # устаревшую офлайн-запись нельзя использовать, чтобы откатить профиль назад
        profile = apply_profile_update(
            user,
            {
                "season_period": answers["season_period"],
                "trainings_per_week": answers["trainings_per_week"],
                "hours_per_week": Decimal(str(answers["hours_per_week"])),
            },
            changed_at=filled_at,
        )

    ev = evaluate(answers, cfg)
    due = local_date + timedelta(days=next_due_days(ev.red_flag, ev.urgent, cfg))

    bp, hrv, th = answers["bp"], answers["hrv"], cfg["thresholds"]
    kerdo = klass = None
    if bp["measured"]:
        kerdo = kerdo_index(bp["dbp"], bp["pulse"])
        klass = kerdo_class(kerdo, th["kerdo_low"], th["kerdo_high"])

    restq = answers.get("restq")
    stored = {k: v for k, v in answers.items() if k != "restq"}

    rec = SelfAssessment.objects.create(
        user=user,
        client_uuid=data["client_uuid"],
        filled_at=filled_at,
        age=age_on(profile.birth_date, local_date),
        sport=profile.sport_snapshot(),
        trainings_per_week=answers["trainings_per_week"],
        hours_per_week=Decimal(str(answers["hours_per_week"])),
        season_period=answers["season_period"],
        tolerance=answers["tolerance"],
        restq_filled=bool(restq),
        bp_measured=bp["measured"],
        sbp=bp.get("sbp"),
        dbp=bp.get("dbp"),
        pulse=bp.get("pulse"),
        kerdo_index=kerdo,
        kerdo_class=klass or "",
        hrv_has_device=hrv["has_device"],
        hrv_value=hrv.get("value"),
        hrv_metric=hrv.get("metric", ""),
        hrv_device=hrv.get("device", ""),
        hrv_date=hrv.get("date"),
        hrv_conditions=hrv.get("conditions", ""),
        answers=stored,
        red_flag=ev.red_flag,
        urgent=ev.urgent,
        reasons=ev.reasons,
        next_due_date=due,
        settings_version=settings_obj,
    )
    if restq:
        res = restq_score(restq["answers"])
        RestqResult.objects.create(
            assessment=rec,
            timing=restq["timing"],
            answers=restq["answers"],
            scales=res["scales"],
            blocks=res["blocks"],
            total_stress=res["total_stress"],
            total_recovery=res["total_recovery"],
            balance=res["balance"],
        )

    AssessmentDraft.objects.filter(user=user).delete()
    if is_latest:
        schedule_next(user, due, cfg)
    return rec
