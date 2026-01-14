# from django.urls import path
# from rest_framework_simplejwt.views import TokenRefreshView
# from .views import RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView

# urlpatterns = [
#     # Auth
#     path("auth/register/", RegisterView.as_view(), name="register"),
#     path("auth/verify-otp/", VerifyOtpView.as_view(), name="verify_otp"),
#     path("auth/resend-otp/", ResendOtpView.as_view(), name="resend_otp"),

#     path("auth/login/", LoginView.as_view(), name="login"),
#     path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),

#     path("auth/me/", MeView.as_view(), name="me"),
# ]

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView,
    AttendanceMarkView, MyAttendanceListView, TodayAttendanceStatusView, AdminOfficeListCreateView, AdminOfficeUpdateView,
    AdminGenerateOfficeQRView, AdminGetOfficeQRView,
)

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/verify-otp/", VerifyOtpView.as_view(), name="verify_otp"),
    path("auth/resend-otp/", ResendOtpView.as_view(), name="resend_otp"),

    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("auth/me/", MeView.as_view(), name="me"),

    # Attendance
    path("attendance/mark/", AttendanceMarkView.as_view(), name="attendance_mark"),
    path("attendance/me/", MyAttendanceListView.as_view(), name="my_attendance_list"),
    path("attendance/today/", TodayAttendanceStatusView.as_view(), name="today_attendance_status"),
    path("admin/offices/", AdminOfficeListCreateView.as_view(), name="admin_offices"),
    path("admin/offices/<int:office_id>/", AdminOfficeUpdateView.as_view(), name="admin_office_update"),
    path("admin/offices/<int:office_id>/generate-qr/", AdminGenerateOfficeQRView.as_view(), name="admin_generate_office_qr"),
    path("admin/offices/<int:office_id>/qr/", AdminGetOfficeQRView.as_view(), name="admin_get_office_qr"),
]
