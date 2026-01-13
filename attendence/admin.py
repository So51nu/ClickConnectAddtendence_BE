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
