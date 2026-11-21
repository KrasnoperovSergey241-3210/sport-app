import json
import uuid
from datetime import date, timedelta

from django.db import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import audit
from apps.core.permissions import IsAthlete
from apps.core.settings_service import get_active_settings
from apps.profiles.models import AthleteProfile, ProfileChange
from apps.profiles.serializers import ProfileChangeSerializer
from apps.profiles.services import get_names
from apps.reminders.services import get_schedule, tz_of

from .models import AssessmentDraft, SelfAssessment
from .presenters import assessment_dict
from .serializers import AnswersSerializer, CompleteSerializer
from .services import complete_assessment


def _qs(user):
    return SelfAssessment.objects.filter(user=user).select_related("restq", "settings_version")


def _filter_period(qs, request):
    d_from, d_to = parse_date(request.query_params.get("from", "")), parse_date(request.query_params.get("to", ""))
    if d_from:
        qs = qs.filter(filled_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(filled_at__date__lte=d_to)
    return qs


class AssessmentListCreateView(APIView):
    permission_classes = [IsAthlete]

    def get(self, request):
        """История: GET /api/assessments/?from=2026-01-01&to=2026-11-21 (новые — первыми)."""
        items = [assessment_dict(r) for r in _filter_period(_qs(request.user), request)]
        audit(request, "read_list", "assessment", request.user.code, count=len(items))
        return Response(items)

    def post(self, request):
        """Завершить самооценку. Повторная отправка того же client_uuid безопасна (вернёт ту же запись)."""
        try:
            cu = uuid.UUID(str(request.data.get("client_uuid")))
            existing = _qs(request.user).filter(client_uuid=cu).first()
            if existing:
                return Response(assessment_dict(existing, full=True))
        except ValueError:
            pass
        cfg = get_active_settings()
        s = CompleteSerializer(data=request.data, context={"cfg": cfg.data})
        s.is_valid(raise_exception=True)
        try:
            rec = complete_assessment(request.user, s.validated_data, cfg)
        except IntegrityError:  # параллельная повторная отправка
            rec = _qs(request.user).get(client_uuid=s.validated_data["client_uuid"])
            return Response(assessment_dict(rec, full=True))
        rec = _qs(request.user).get(pk=rec.pk)
        audit(request, "create", "assessment", rec.id, red_flag=rec.red_flag, urgent=rec.urgent)
        return Response(assessment_dict(rec, full=True), status=status.HTTP_201_CREATED)


class AssessmentDetailView(APIView):
    """Просмотр записи только для чтения (включая результаты RESTQ-Sport). PUT/PATCH/DELETE не существуют."""

    permission_classes = [IsAthlete]

    def get(self, request, pk):
        rec = _qs(request.user).filter(pk=pk).first()
        if not rec:
            raise NotFound("Запись не найдена")
        audit(request, "read", "assessment", rec.id)
        return Response(assessment_dict(rec, full=True))


class DraftView(APIView):
    """Черновик (72 часа): GET — продолжить, PUT {"data": {...}} — сохранить, DELETE — сбросить."""

    permission_classes = [IsAthlete]
    MAX_BYTES = 200_000
    EXTRA_KEYS = {"step", "client_uuid", "started_at"}

    def _get(self, user):
        d = AssessmentDraft.objects.filter(user=user).first()
        if d and d.expires_at <= timezone.now():
            d.delete()
            return None
        return d

    def get(self, request):
        d = self._get(request.user)
        if not d:
            raise NotFound("Черновика нет")
        return Response({"data": d.data, "updated_at": d.updated_at, "expires_at": d.expires_at})

    def put(self, request):
        data = request.data.get("data")
        if not isinstance(data, dict):
            raise ValidationError({"data": ["Ожидается объект"]})
        if len(json.dumps(data)) > self.MAX_BYTES:
            raise ValidationError({"data": ["Слишком большой черновик"]})
        allowed = set(AnswersSerializer().fields) | self.EXTRA_KEYS
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValidationError({"data": [f"Неизвестные поля: {', '.join(unknown)}"]})
        ttl = get_active_settings().data["drafts"]["ttl_hours"]
        d, _ = AssessmentDraft.objects.update_or_create(
            user=request.user, defaults={"data": data, "expires_at": timezone.now() + timedelta(hours=ttl)}
        )
        return Response({"updated_at": d.updated_at, "expires_at": d.expires_at})

    def delete(self, request):
        AssessmentDraft.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HomeView(APIView):
    """Данные главного экрана (ТЗ п. 5.3)."""

    permission_classes = [IsAthlete]

    def get(self, request):
        user = request.user
        profile = AthleteProfile.objects.get(user=user)
        names = get_names(user)
        today = timezone.now().astimezone(tz_of(get_schedule(user).timezone)).date()
        last = _qs(user).first()
        since = today - timedelta(days=183)
        series = _qs(user).filter(filled_at__date__gte=since).order_by("filled_at")
        data = {
            "first_name": names["first_name"],
            "season_period": profile.season_period,
            "profile_complete": profile.is_complete,
            "last_assessment": None,
            "next_assessment": None,
            "tolerance_6m": [{"date": r.filled_at, "tolerance": r.tolerance} for r in series],
        }
        if last:
            data["last_assessment"] = {
                "id": str(last.id),
                "filled_at": last.filled_at,
                "red_flag": last.red_flag,
                "urgent": last.urgent,
                "reasons": [r["text"] for r in last.reasons],
            }
            left = (last.next_due_date - today).days
            data["next_assessment"] = {"date": last.next_due_date, "days_left": left, "overdue": left < 0}
        return Response(data)


class ExportDataView(APIView):
    """Данные для выгрузки в Excel (файл формирует клиент, ТЗ п. 5.7).

    GET /api/export/data/?from=&to=&include_name=1 — ФИО отдаются только при include_name=1.
    """

    permission_classes = [IsAthlete]

    def get(self, request):
        user = request.user
        include_name = request.query_params.get("include_name") in ("1", "true", "True")
        p = AthleteProfile.objects.select_related("sport").get(user=user)
        profile = {
            "user_code": str(user.code),
            "sex": p.sex,
            "birth_date": p.birth_date,
            "sport": p.sport_snapshot(),
            "start_age_any": p.start_age_any,
            "start_age_sport": p.start_age_sport,
            "total_experience": None if p.start_age_any is None else p.age() - p.start_age_any,
            "sport_experience": None if p.start_age_sport is None else p.age() - p.start_age_sport,
            "trainings_per_week": p.trainings_per_week,
            "hours_per_week": None if p.hours_per_week is None else float(p.hours_per_week),
        }
        if include_name:
            profile.update(get_names(user))
        items = [assessment_dict(r, full=True) for r in _filter_period(_qs(user), request)]
        changes = ProfileChangeSerializer(ProfileChange.objects.filter(user=user), many=True).data
        audit(request, "export", "assessment", user.code, include_name=include_name, count=len(items))
        return Response(
            {
                "exported_at": timezone.now(),
                "profile": profile,
                "profile_changes": changes,
                "assessments": items,
            }
        )
