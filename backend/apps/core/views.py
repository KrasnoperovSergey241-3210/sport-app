from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .settings_service import get_active_settings


class PublicSettingsView(APIView):
    """Действующие пороги, сроки и тексты. Клиент кэширует их для офлайн-режима."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def get(self, request):
        s = get_active_settings()
        return Response({"version": s.version, "data": s.data})
