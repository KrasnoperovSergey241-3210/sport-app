from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAthlete
from apps.core.settings_service import get_active_settings

from .models import DeviceToken
from .services import get_schedule, reschedule_current


class ReminderSettingsSerializer(serializers.Serializer):
    notify_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    timezone = serializers.CharField(max_length=64)

    def validate_timezone(self, v):
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Неизвестный часовой пояс (пример: Europe/Moscow)")
        return v


class ReminderSettingsView(APIView):
    """Время напоминаний (экран «Настройки»). По умолчанию 09:00 местного времени."""

    permission_classes = [IsAthlete]

    def _out(self, sch):
        return {
            "notify_time": sch.notify_time.strftime("%H:%M"),
            "timezone": sch.timezone,
            "due_date": sch.due_date,
        }

    def get(self, request):
        return Response(self._out(get_schedule(request.user)))

    def put(self, request):
        s = ReminderSettingsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        sch = get_schedule(request.user)
        sch.notify_time = s.validated_data["notify_time"]
        sch.timezone = s.validated_data["timezone"]
        reschedule_current(sch, get_active_settings().data)
        return Response(self._out(sch))


class DeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(choices=DeviceToken.Platform.choices)


class DeviceView(APIView):
    """Регистрация push-токена устройства. DELETE {token} — при выходе из аккаунта."""

    permission_classes = [IsAthlete]

    def post(self, request):
        s = DeviceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        DeviceToken.objects.update_or_create(
            token=s.validated_data["token"],
            defaults={"user": request.user, "platform": s.validated_data["platform"]},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        DeviceToken.objects.filter(user=request.user, token=request.data.get("token", "")).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
