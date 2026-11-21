from django.urls import path

from . import views as v

urlpatterns = [
    path("sports/", v.SportListView.as_view()),
    path("profile/", v.ProfileView.as_view()),
    path("profile/season/", v.SeasonView.as_view()),
    path("profile/history/", v.ProfileHistoryView.as_view()),
]
