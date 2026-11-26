from django.urls import path

from . import views as v

urlpatterns = [
    path("auth/register/", v.RegisterView.as_view()),
    path("auth/register/start/", v.RegisterStartView.as_view()),
    path("auth/register/verify/", v.RegisterVerifyView.as_view()),
    path("auth/login/", v.LoginView.as_view()),
    path("auth/login/otp/start/", v.LoginOtpStartView.as_view()),
    path("auth/login/otp/verify/", v.LoginOtpVerifyView.as_view()),
    path("auth/password-reset/start/", v.PasswordResetStartView.as_view()),
    path("auth/password-reset/confirm/", v.PasswordResetConfirmView.as_view()),
    path("auth/token/refresh/", v.RefreshView.as_view()),
    path("auth/logout/", v.LogoutView.as_view()),
    path("account/", v.AccountView.as_view()),
    path("account/consent/revoke/", v.RevokeConsentView.as_view()),
]
