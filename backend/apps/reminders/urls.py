from django.urls import path

from . import views as v

urlpatterns = [
    path("reminders/settings/", v.ReminderSettingsView.as_view()),
    path("devices/", v.DeviceView.as_view()),
]
