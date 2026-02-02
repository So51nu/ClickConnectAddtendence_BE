from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email=email, password=password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=120, blank=True)

    phone = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)   # 👈 IMPORTANT
    is_verified = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()


    def __str__(self):
        return self.email


class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    employee_code = models.CharField(max_length=30, blank=True)
    phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{10}$", "Phone must be 10 digits.")]
    )

    department = models.CharField(max_length=80, blank=True)
    designation = models.CharField(max_length=80, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile({self.user.email})"


class EmailOTP(models.Model):
    """
    OTP store as hash (security). One purpose for now: REGISTER_VERIFY
    """
    PURPOSE_REGISTER_VERIFY = "REGISTER_VERIFY"
    PURPOSE_CHOICES = [(PURPOSE_REGISTER_VERIFY, "Register Verify")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_REGISTER_VERIFY)

    otp_hash = models.CharField(max_length=128)
    salt = models.CharField(max_length=32)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    send_count = models.PositiveIntegerField(default=1)
    last_sent_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email", "purpose", "is_used"]),
        ]

    def __str__(self):
        return f"OTP({self.email}, {self.purpose}, used={self.is_used})"

from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid

# ... tumhare existing User, EmployeeProfile, EmailOTP models same rahenge ...


class OfficeLocation(models.Model):
    """
    Admin created office/site with allowed geo radius
    """
    name = models.CharField(max_length=120)
    address = models.TextField(blank=True)

    latitude = models.FloatField()
    longitude = models.FloatField()
    allowed_radius_m = models.PositiveIntegerField(default=100)  # meters

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.allowed_radius_m}m)"


class OfficeQR(models.Model):
    """
    Static QR token for an office.
    QR me yahi token encode hoga.
    """
    office = models.OneToOneField(OfficeLocation, on_delete=models.CASCADE, related_name="qr")
    qr_token = models.CharField(max_length=80, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR({self.office.name})"


class Attendance(models.Model):
    SOURCE_ONLINE = "ONLINE"
    SOURCE_OFFLINE = "OFFLINE"
    SOURCE_CHOICES = [(SOURCE_ONLINE, "Online"), (SOURCE_OFFLINE, "Offline")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendances")
    office = models.ForeignKey(OfficeLocation, on_delete=models.PROTECT, related_name="attendances")

    date = models.DateField(db_index=True)

    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    check_in_lat = models.FloatField(null=True, blank=True)
    check_in_lng = models.FloatField(null=True, blank=True)
    check_in_accuracy_m = models.FloatField(null=True, blank=True)

    check_out_lat = models.FloatField(null=True, blank=True)
    check_out_lng = models.FloatField(null=True, blank=True)
    check_out_accuracy_m = models.FloatField(null=True, blank=True)

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_ONLINE)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")  # per day one attendance record
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["office", "date"]),
        ]

    def __str__(self):
        return f"Attendance({self.user.email}, {self.date}, {self.office.name})"


from django.db import models
from django.conf import settings
from django.utils import timezone

class LeaveRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_requests")
    from_date = models.DateField()
    to_date = models.DateField()
    leave_type = models.CharField(max_length=30, default="CASUAL")  # CASUAL/SICK/etc
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    admin_comment = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="leave_decisions"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "created_at"])]

    def __str__(self):
        return f"Leave({self.user.email}, {self.from_date} - {self.to_date}, {self.status})"


class RegularizationRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="regularizations")
    date = models.DateField()
    requested_check_in = models.DateTimeField(null=True, blank=True)
    requested_check_out = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    admin_comment = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="regularization_decisions"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "date", "status"])]

    def __str__(self):
        return f"Regularization({self.user.email}, {self.date}, {self.status})"


class ResignationRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resignations")
    last_working_date = models.DateField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    admin_comment = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resignation_decisions"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "created_at"])]

    def __str__(self):
        return f"Resignation({self.user.email}, {self.last_working_date}, {self.status})"


class EmployeeDocument(models.Model):
    DOC_AADHAR = "AADHAR"
    DOC_PAN = "PAN"
    DOC_ESIC = "ESIC"
    DOC_OTHER = "OTHER"
    DOC_TYPE_CHOICES = [
        (DOC_AADHAR, "Aadhar"),
        (DOC_PAN, "PAN"),
        (DOC_ESIC, "ESIC"),
        (DOC_OTHER, "Other"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default=DOC_OTHER)
    title = models.CharField(max_length=120, blank=True, default="")
    file = models.FileField(upload_to="employee_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "doc_type", "uploaded_at"])]

    def __str__(self):
        return f"Doc({self.user.email}, {self.doc_type})"


class ESICProfile(models.Model):
    """
    ESIC details for employee (admin/user can update)
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="esic")
    esic_number = models.CharField(max_length=40, blank=True, default="")
    dispensary = models.CharField(max_length=120, blank=True, default="")
    branch_office = models.CharField(max_length=120, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ESIC({self.user.email})"


class OfflineAttendanceRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="offline_attendance_requests")
    office = models.ForeignKey("OfficeLocation", on_delete=models.PROTECT, related_name="offline_requests")

    date = models.DateField()
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    admin_comment = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="offline_decisions"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "date", "status"])]

    def __str__(self):
        return f"OfflineReq({self.user.email}, {self.date}, {self.status})"


class RosterShift(models.Model):
    """
    Admin-defined shifts
    """
    name = models.CharField(max_length=60)  # e.g. Morning
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"


class RosterAssignment(models.Model):
    """
    Assign shift to a user on a date
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roster_assignments")
    office = models.ForeignKey("OfficeLocation", on_delete=models.PROTECT, related_name="roster_assignments")
    date = models.DateField(db_index=True)
    shift = models.ForeignKey(RosterShift, on_delete=models.PROTECT, related_name="assignments")
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        indexes = [models.Index(fields=["office", "date"])]

    def __str__(self):
        return f"Roster({self.user.email}, {self.date}, {self.shift.name})"


# models.py (add at bottom)

from django.db import models
from django.conf import settings

class DailyReport(models.Model):
    STATUS_DONE = "DONE"
    STATUS_PROGRESS = "PROGRESS"
    STATUS_PENDING = "PENDING"
    STATUS_CHOICES = [
        (STATUS_DONE, "Done"),
        (STATUS_PROGRESS, "In Progress"),
        (STATUS_PENDING, "Pending"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_reports")
    report_date = models.DateField(db_index=True)  # ✅ jis date ka report hai
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["report_date", "status"]),
            models.Index(fields=["user", "report_date"]),
        ]
        ordering = ["-report_date", "-created_at"]

    def __str__(self):
        return f"DailyReport({self.user.email}, {self.report_date}, {self.status})"
