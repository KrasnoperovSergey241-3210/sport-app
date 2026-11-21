from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.audit import audit
from apps.core.permissions import IsAthlete

from .models import AthleteProfile, ProfileChange, Sport
from .serializers import NAME_FIELDS, ProfileChangeSerializer, ProfileSerializer, SeasonSerializer, SportSerializer
from .services import apply_profile_update, get_names, set_names


class SportListView(ListAPIView):
    """Справочник с поиском по названию: GET /api/sports/?q=бег"""

    permission_classes = [IsAthlete]
    serializer_class = SportSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Sport.objects.filter(is_active=True)
        q = self.request.query_params.get("q", "").strip()
        return qs.filter(name__icontains=q) if q else qs


class ProfileView(APIView):
    permission_classes = [IsAthlete]

    def _profile(self, user):
        return AthleteProfile.objects.select_related("sport").get(user=user)

    def get(self, request):
        p = self._profile(request.user)
        audit(request, "read", "profile", request.user.code)
        return Response(ProfileSerializer(p, context={"names": get_names(request.user)}).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        p = self._profile(request.user)
        s = ProfileSerializer(p, data=request.data, partial=partial)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        names = {k: data.pop(k) for k in NAME_FIELDS if k in data}
        set_names(request.user, names)
        p = apply_profile_update(request.user, data)
        audit(request, "update", "profile", request.user.code, fields=sorted(list(data) + list(names)))
        return Response(ProfileSerializer(p, context={"names": get_names(request.user)}).data)


class SeasonView(APIView):
    """Смена периода сезона в одно касание (с записью в историю)."""

    permission_classes = [IsAthlete]

    def put(self, request):
        s = SeasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        p = apply_profile_update(request.user, {"season_period": s.validated_data["season_period"]})
        audit(request, "update", "profile", request.user.code, fields=["season_period"])
        return Response({"season_period": p.season_period})

    patch = put


class ProfileHistoryView(ListAPIView):
    permission_classes = [IsAthlete]
    serializer_class = ProfileChangeSerializer
    pagination_class = None

    def get_queryset(self):
        return ProfileChange.objects.filter(user=self.request.user)
