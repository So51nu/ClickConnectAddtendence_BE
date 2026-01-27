# # from django.urls import path
# # from rest_framework_simplejwt.views import TokenRefreshView
# # from .views import RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView

# # urlpatterns = [
# #     # Auth
# #     path("auth/register/", RegisterView.as_view(), name="register"),
# #     path("auth/verify-otp/", VerifyOtpView.as_view(), name="verify_otp"),
# #     path("auth/resend-otp/", ResendOtpView.as_view(), name="resend_otp"),

# #     path("auth/login/", LoginView.as_view(), name="login"),
# #     path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),

# #     path("auth/me/", MeView.as_view(), name="me"),
# # ]

# from django.urls import path
# from rest_framework_simplejwt.views import TokenRefreshView

# from .views import (
#     RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView,
#     AttendanceMarkView, MyAttendanceListView, TodayAttendanceStatusView, AdminOfficeListCreateView, AdminOfficeUpdateView,
#     AdminGenerateOfficeQRView, AdminGetOfficeQRView,
# )

# urlpatterns = [
#     # Auth
#     path("auth/register/", RegisterView.as_view(), name="register"),
#     path("auth/verify-otp/", VerifyOtpView.as_view(), name="verify_otp"),
#     path("auth/resend-otp/", ResendOtpView.as_view(), name="resend_otp"),

#     path("auth/login/", LoginView.as_view(), name="login"),
#     path("auth/refresh/", TokenRefreshView.as_view(), name="refresh"),
#     path("auth/me/", MeView.as_view(), name="me"),

#     # Attendance
#     path("attendance/mark/", AttendanceMarkView.as_view(), name="attendance_mark"),
#     path("attendance/me/", MyAttendanceListView.as_view(), name="my_attendance_list"),
#     path("attendance/today/", TodayAttendanceStatusView.as_view(), name="today_attendance_status"),
#     path("admin/offices/", AdminOfficeListCreateView.as_view(), name="admin_offices"),
#     path("admin/offices/<int:office_id>/", AdminOfficeUpdateView.as_view(), name="admin_office_update"),
#     path("admin/offices/<int:office_id>/generate-qr/", AdminGenerateOfficeQRView.as_view(), name="admin_generate_office_qr"),
#     path("admin/offices/<int:office_id>/qr/", AdminGetOfficeQRView.as_view(), name="admin_get_office_qr"),
# ]

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView, VerifyOtpView, ResendOtpView, LoginView, MeView,
    AttendanceMarkView, MyAttendanceListView, TodayAttendanceStatusView,
    AdminOfficeListCreateView, AdminOfficeUpdateView, AdminGenerateOfficeQRView, AdminGetOfficeQRView,

    # NEW
    MyLeaveListCreateView, AdminLeaveListView, AdminLeaveDecideView,
    MyRegularizationListCreateView, AdminRegularizationListView, AdminRegularizationDecideView,
    MyResignationListCreateView, AdminResignationListView, AdminResignationDecideView,
    MyDocumentListCreateView, MyDocumentDeleteView,
    MyESICView,
    MyOfflineAttendanceListCreateView, AdminOfflineAttendanceListView, AdminOfflineAttendanceDecideView,
    MyRosterView, AdminShiftListCreateView, AdminRosterAssignView, AdminUserListView,
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

    # Admin Offices
    path("admin/offices/", AdminOfficeListCreateView.as_view(), name="admin_offices"),
    path("admin/offices/<int:office_id>/", AdminOfficeUpdateView.as_view(), name="admin_office_update"),
    path("admin/offices/<int:office_id>/generate-qr/", AdminGenerateOfficeQRView.as_view(), name="admin_generate_office_qr"),
    path("admin/offices/<int:office_id>/qr/", AdminGetOfficeQRView.as_view(), name="admin_get_office_qr"),

    # ✅ Leaves
    path("leave/me/", MyLeaveListCreateView.as_view(), name="leave_me"),
    path("admin/leave/", AdminLeaveListView.as_view(), name="admin_leave_list"),
    path("admin/leave/<int:leave_id>/decide/", AdminLeaveDecideView.as_view(), name="admin_leave_decide"),
    path("admin/users/", AdminUserListView.as_view(), name="admin_users"),
    # ✅ Regularization
    path("regularization/me/", MyRegularizationListCreateView.as_view(), name="regularization_me"),
    path("admin/regularization/", AdminRegularizationListView.as_view(), name="admin_regularization_list"),
    path("admin/regularization/<int:req_id>/decide/", AdminRegularizationDecideView.as_view(), name="admin_regularization_decide"),

    # ✅ Resignation
    path("resignation/me/", MyResignationListCreateView.as_view(), name="resignation_me"),
    path("admin/resignation/", AdminResignationListView.as_view(), name="admin_resignation_list"),
    path("admin/resignation/<int:req_id>/decide/", AdminResignationDecideView.as_view(), name="admin_resignation_decide"),

    # ✅ Documents
    path("documents/me/", MyDocumentListCreateView.as_view(), name="documents_me"),
    path("documents/me/<int:doc_id>/", MyDocumentDeleteView.as_view(), name="documents_delete"),

    # ✅ ESIC
    path("esic/me/", MyESICView.as_view(), name="esic_me"),

    # ✅ Offline attendance request
    path("offline-attendance/me/", MyOfflineAttendanceListCreateView.as_view(), name="offline_attendance_me"),
    path("admin/offline-attendance/", AdminOfflineAttendanceListView.as_view(), name="admin_offline_attendance_list"),
    path("admin/offline-attendance/<int:req_id>/decide/", AdminOfflineAttendanceDecideView.as_view(), name="admin_offline_attendance_decide"),

    # ✅ Roster
    path("roster/me/", MyRosterView.as_view(), name="roster_me"),
    path("admin/roster/shifts/", AdminShiftListCreateView.as_view(), name="admin_roster_shifts"),
    path("admin/roster/assign/", AdminRosterAssignView.as_view(), name="admin_roster_assign"),
]
