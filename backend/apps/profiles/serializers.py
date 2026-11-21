from django.utils import timezone
from rest_framework import serializers

from apps.core.utils import age_on

from .models import AthleteProfile, ProfileChange, Sport

NAME_FIELDS = ("last_name", "first_name", "middle_name")


class SportSerializer(serializers.ModelSerializer):
    """Пользователю показывается только название (характеристики в API не отдаём)."""

    class Meta:
        model = Sport
        fields = ("id", "name")


class ProfileSerializer(serializers.ModelSerializer):
    last_name = serializers.CharField(max_length=100, required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    sport = serializers.PrimaryKeyRelatedField(
        queryset=Sport.objects.filter(is_active=True), required=False, allow_null=True
    )
    hours_per_week = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=0, max_value=60, required=False)
    trainings_per_week = serializers.IntegerField(min_value=0, max_value=21, required=False)
    start_age_any = serializers.IntegerField(min_value=0, max_value=100, required=False)
    start_age_sport = serializers.IntegerField(min_value=0, max_value=100, required=False)
    age = serializers.SerializerMethodField()
    sport_name = serializers.SerializerMethodField()
    total_experience = serializers.SerializerMethodField()
    sport_experience = serializers.SerializerMethodField()
    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = AthleteProfile
        fields = (
            *NAME_FIELDS, "sex", "birth_date", "sport", "sport_custom", "sport_name",
            "start_age_any", "start_age_sport", "trainings_per_week", "hours_per_week", "season_period",
            "age", "total_experience", "sport_experience", "is_complete",
        )
        extra_kwargs = {"sex": {"required": False}, "season_period": {"required": False}, "birth_date": {"required": False}}

    def get_age(self, obj):
        return obj.age()

    def get_sport_name(self, obj):
        return obj.sport_name()

    def get_total_experience(self, obj):
        return None if obj.start_age_any is None else obj.age() - obj.start_age_any

    def get_sport_experience(self, obj):
        return None if obj.start_age_sport is None else obj.age() - obj.start_age_sport

    def to_representation(self, obj):
        data = super().to_representation(obj)
        data.update(self.context.get("names", {}))
        return data

    def validate_hours_per_week(self, v):
        if (v * 2) % 1 != 0:
            raise serializers.ValidationError("Шаг — 0,5 часа")
        return v

    def validate(self, attrs):
        inst = self.instance
        cur = lambda k: attrs[k] if k in attrs else getattr(inst, k, None)  # noqa: E731
        full = not self.partial
        # обязательные поля при полном сохранении (PUT)
        required = ["first_name", "last_name", "sex", "start_age_any", "start_age_sport", "trainings_per_week", "hours_per_week"]
        if full:
            missing = {k: ["Обязательное поле"] for k in required if k not in attrs}
            if missing:
                raise serializers.ValidationError(missing)
        # вид спорта: либо справочник, либо «Другой» с ручным вводом
        if "sport" in attrs or "sport_custom" in attrs or full:
            if (attrs.get("sport_custom") or "").strip() and "sport" not in attrs:
                attrs["sport"] = None  # выбран вариант «Другой»
            sport, custom = cur("sport"), (cur("sport_custom") or "").strip()
            if "sport" in attrs and attrs["sport"] is not None:
                attrs["sport_custom"] = ""
                custom = ""
            if not sport and not custom:
                raise serializers.ValidationError({"sport": ["Выберите вид спорта или укажите свой вариант"]})
            if "sport_custom" in attrs:
                attrs["sport_custom"] = attrs["sport_custom"].strip()
        # возраст начала занятий
        age = age_on(cur("birth_date"), timezone.localdate())
        if age < 18:
            raise serializers.ValidationError({"birth_date": ["Приложение предназначено для спортсменов 18 лет и старше"]})
        a_any, a_sport = cur("start_age_any"), cur("start_age_sport")
        if a_any is not None and a_any > age:
            raise serializers.ValidationError({"start_age_any": ["Не может быть больше текущего возраста"]})
        if a_sport is not None:
            if a_sport > age:
                raise serializers.ValidationError({"start_age_sport": ["Не может быть больше текущего возраста"]})
            if a_any is not None and a_sport < a_any:
                raise serializers.ValidationError(
                    {"start_age_sport": ["Не может быть меньше возраста начала занятий спортом вообще"]}
                )
        return attrs


class SeasonSerializer(serializers.Serializer):
    season_period = serializers.ChoiceField(choices=AthleteProfile.Season.choices)


class ProfileChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileChange
        fields = ("field", "old_value", "new_value", "changed_at")
