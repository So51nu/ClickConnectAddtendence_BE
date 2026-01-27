from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmployeeProfile, EmailOTP


class UserAdmin(BaseUserAdmin):
    ordering = ["id"]
    list_display = ["email", "full_name", "is_active", "is_verified", "is_staff", "date_joined"]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name",)}),
        ("Permissions", {"fields": ("is_active", "is_verified", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )

    def get_fieldsets(self, request, obj=None):
        return super().get_fieldsets(request, obj)


admin.site.register(User, UserAdmin)
admin.site.register(EmployeeProfile)
admin.site.register(EmailOTP)
from django.contrib import admin
from .models import OfficeLocation, OfficeQR, Attendance

@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "latitude", "longitude", "allowed_radius_m", "is_active", "created_at")
    search_fields = ("name",)

@admin.register(OfficeQR)
class OfficeQRAdmin(admin.ModelAdmin):
    list_display = ("id", "office", "qr_token", "is_active", "created_at")
    search_fields = ("qr_token", "office__name")

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "office", "date", "check_in_time", "check_out_time", "source")
    list_filter = ("office", "date", "source")
    search_fields = ("user__email", "office__name")

from django.contrib import admin
from .models import (
    LeaveRequest, RegularizationRequest, ResignationRequest,
    EmployeeDocument, ESICProfile, OfflineAttendanceRequest,
    RosterShift, RosterAssignment
)

admin.site.register(LeaveRequest)
admin.site.register(RegularizationRequest)
admin.site.register(ResignationRequest)
admin.site.register(EmployeeDocument)
admin.site.register(ESICProfile)
admin.site.register(OfflineAttendanceRequest)
admin.site.register(RosterShift)
admin.site.register(RosterAssignment)
