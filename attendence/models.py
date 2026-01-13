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

    # ✅ account flags
    is_active = models.BooleanField(default=False)   # OTP verify ke baad True
    is_verified = models.BooleanField(default=False) # OTP verify ke baad True
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
