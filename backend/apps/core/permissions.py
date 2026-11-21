from rest_framework.permissions import BasePermission


class IsAthlete(BasePermission):
    """Только спортсмен. Администратор к данным спортсменов доступа не имеет."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.role == "athlete")
