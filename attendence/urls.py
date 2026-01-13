from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", VerifyOtpView.as_view(), name="verify_otp"),
    path("auth/resend-otp/", ResendOtpView.as_view(), name="resend_otp"),

    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),

    path("auth/me/", MeView.as_view(), name="me"),
]
