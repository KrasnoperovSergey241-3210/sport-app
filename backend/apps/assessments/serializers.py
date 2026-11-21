from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.profiles.models import AthleteProfile

from .scoring import RESTQ_ITEMS, YESNO_FLAG_QUESTIONS, answer_key

COMMENT_SECTIONS = (2, 3, 4, 5, 6)


class BpSerializer(serializers.Serializer):
    measured = serializers.BooleanField()
    sbp = serializers.IntegerField(min_value=60, max_value=250, required=False)
    dbp = serializers.IntegerField(min_value=40, max_value=150, required=False)
    pulse = serializers.IntegerField(min_value=30, max_value=200, required=False)

    def validate(self, a):
        if not a["measured"]:  # «Нет возможности измерить»: значения не сохраняются
            return {"measured": False}
        missing = {k: ["Обязательное поле"] for k in ("sbp", "dbp", "pulse") if k not in a}
        if missing:
            raise serializers.ValidationError(missing)
        if a["sbp"] <= a["dbp"]:
            raise serializers.ValidationError({"sbp": ["САД должно быть больше ДАД"]})
        return a


class HrvSerializer(serializers.Serializer):
    has_device = serializers.BooleanField()
    value = serializers.FloatField(min_value=5, max_value=300, required=False)
    metric = serializers.ChoiceField(["rmssd", "sdnn", "unknown"], required=False)
    device = serializers.CharField(max_length=100, required=False, allow_blank=True)
    date = serializers.DateField(required=False)
    conditions = serializers.ChoiceField(["morning", "night", "other"], required=False)

    def validate(self, a):
        if not a["has_device"]:  # раздел 8 пропускается, на итог не влияет
            return {"has_device": False}
        missing = {k: ["Обязательное поле"] for k in ("value", "metric", "conditions") if k not in a}
        if missing:
            raise serializers.ValidationError(missing)
        return a


class RestqSerializer(serializers.Serializer):
    timing = serializers.ChoiceField(["before", "after"])
    answers = serializers.DictField(child=serializers.IntegerField(min_value=0, max_value=6))

    def validate_answers(self, v):
        if set(v.keys()) != {str(i) for i in range(1, RESTQ_ITEMS + 1)}:
            raise serializers.ValidationError("Нужны ответы на все 77 утверждений (ключи «1»…«77»)")
        return v


class AnswersSerializer(serializers.Serializer):
    season_period = serializers.ChoiceField(choices=AthleteProfile.Season.choices)
    trainings_per_week = serializers.IntegerField(min_value=0, max_value=21)  # подтверждено/исправлено в начале анкеты
    hours_per_week = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=0, max_value=60)
    tolerance = serializers.IntegerField(min_value=1, max_value=5)  # вопрос 2.1
    restq = RestqSerializer(required=False, allow_null=True)
    q3_3_detail = serializers.ListField(child=serializers.ChoiceField(["syncope", "dizziness"]), required=False)
    q4_2 = serializers.ListField(
        child=serializers.ChoiceField(["fever", "throat", "runny_nose", "cough", "other"]), required=False
    )
    q4_2_other = serializers.CharField(max_length=200, required=False, allow_blank=True)
    q4_3 = serializers.IntegerField(min_value=1, max_value=4, required=False)
    q4_4 = serializers.ChoiceField(["none", "once", "twice_plus"])
    morning_pulse_today = serializers.IntegerField(min_value=30, max_value=200, required=False, allow_null=True)
    morning_pulse_usual = serializers.IntegerField(min_value=30, max_value=200, required=False, allow_null=True)
    bp = BpSerializer()
    hrv = HrvSerializer()

    def get_fields(self):
        fields = super().get_fields()
        for q in YESNO_FLAG_QUESTIONS:  # «да/нет» без ответа по умолчанию — обязательны
            fields[answer_key(q)] = serializers.BooleanField(required=True)
        for n in COMMENT_SECTIONS:
            fields[f"comment_{n}"] = serializers.CharField(max_length=2000, required=False, allow_blank=True)
        return fields

    def validate_hours_per_week(self, v):
        if (v * 2) % 1 != 0:
            raise serializers.ValidationError("Шаг — 0,5 часа")
        return v

    def validate(self, a):
        trigger = self.context["cfg"]["thresholds"]["tolerance_flag_max"]
        if a["tolerance"] <= trigger:
            if not a.get("restq"):
                raise serializers.ValidationError({"restq": ["При оценке 3 балла и ниже нужно заполнить RESTQ-Sport"]})
        else:
            a["restq"] = None  # блок 2А не показывается

        if a["q3_3"]:
            det = list(dict.fromkeys(a.get("q3_3_detail", [])))
            if not det:
                raise serializers.ValidationError({"q3_3_detail": ["Уточните: обморок и/или головокружение"]})
            a["q3_3_detail"] = det
        else:
            a.pop("q3_3_detail", None)

        if a["q4_1"]:
            errs = {}
            if not a.get("q4_2"):
                errs["q4_2"] = ["Выберите, что беспокоило"]
            if "q4_3" not in a:
                errs["q4_3"] = ["Укажите, сколько недель назад (1–4)"]
            if errs:
                raise serializers.ValidationError(errs)
        else:
            for k in ("q4_2", "q4_2_other", "q4_3"):
                a.pop(k, None)
        return a


class CompleteSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    filled_at = serializers.DateTimeField(required=False)  # время завершения на устройстве (офлайн)
    answers = AnswersSerializer()

    def validate_filled_at(self, v):
        now = timezone.now()
        if v > now + timedelta(minutes=5):
            raise serializers.ValidationError("Дата заполнения в будущем")
        if v < now - timedelta(days=90):
            raise serializers.ValidationError("Запись слишком старая для синхронизации")
        return v
