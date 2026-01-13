from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
import hashlib
import secrets
from datetime import timedelta

from .models import User, EmployeeProfile, EmailOTP


def _hash_otp(otp: str, salt: str) -> str:
    return hashlib.sha256(f"{otp}:{salt}".encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    # 6-digit OTP
    return f"{secrets.randbelow(10**6):06d}"


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    full_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=10, required=False, allow_blank=True)

    def validate_email(self, value):
        return value.lower().strip()

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        full_name = validated_data.get("full_name", "")
        phone = validated_data.get("phone", "")

        # If user exists and already verified => block
        existing = User.objects.filter(email=email).first()
        if existing and existing.is_verified:
            raise serializers.ValidationError({"email": "User already exists and verified. Please login."})

        if existing and not existing.is_verified:
            # re-register: update password/name
            user = existing
            user.full_name = full_name or user.full_name
            user.set_password(password)
            user.is_active = False
            user.is_verified = False
            user.save()
        else:
            user = User.objects.create_user(email=email, password=password, full_name=full_name, is_active=False, is_verified=False)

        # Ensure profile exists
        EmployeeProfile.objects.get_or_create(user=user, defaults={"phone": phone})
        if phone:
            profile = user.profile
            profile.phone = phone
            profile.save()

        # OTP throttle: max send per hour + cooldown
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)
        last_otp = EmailOTP.objects.filter(email=email, purpose=EmailOTP.PURPOSE_REGISTER_VERIFY).order_by("-created_at").first()

        if last_otp:
            # cooldown check
            cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
            if (now - last_otp.last_sent_at).total_seconds() < cooldown:
                raise serializers.ValidationError({"detail": f"Please wait {cooldown} seconds before requesting OTP again."})

            # hourly send limit (rough)
            hourly_count = EmailOTP.objects.filter(
                email=email,
                purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
                created_at__gte=one_hour_ago
            ).count()
            max_per_hour = getattr(settings, "OTP_MAX_SEND_PER_HOUR", 5)
            if hourly_count >= max_per_hour:
                raise serializers.ValidationError({"detail": "OTP limit reached. Try again later."})

        otp = _generate_otp()
        salt = secrets.token_hex(8)
        otp_hash = _hash_otp(otp, salt)

        expires_min = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
        expires_at = now + timedelta(minutes=expires_min)

        EmailOTP.objects.create(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            otp_hash=otp_hash,
            salt=salt,
            expires_at=expires_at,
            is_used=False
        )

        # Send email
        subject = "Your Attendance App OTP"
        message = (
            f"Your OTP is: {otp}\n\n"
            f"This OTP will expire in {expires_min} minutes.\n"
            f"If you did not request this, please ignore this email."
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

        return user


class VerifyOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    @transaction.atomic
    def validate(self, attrs):
        email = attrs["email"]
        otp = attrs["otp"].strip()

        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError({"email": "User not found. Please register first."})

        if user.is_verified:
            # already verified
            return attrs

        otp_obj = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            is_used=False
        ).order_by("-created_at").first()

        if not otp_obj:
            raise serializers.ValidationError({"otp": "OTP not found. Please resend OTP."})

        if timezone.now() > otp_obj.expires_at:
            raise serializers.ValidationError({"otp": "OTP expired. Please resend OTP."})

        if _hash_otp(otp, otp_obj.salt) != otp_obj.otp_hash:
            raise serializers.ValidationError({"otp": "Invalid OTP."})

        # Mark verified
        user.is_verified = True
        user.is_active = True
        user.save()

        otp_obj.is_used = True
        otp_obj.save()

        return attrs


class ResendOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()

    @transaction.atomic
    def validate(self, attrs):
        email = attrs["email"]

        user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError({"email": "User not found. Please register first."})

        if user.is_verified:
            raise serializers.ValidationError({"detail": "User already verified. Please login."})

        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)

        # cooldown + per hour limit
        last_otp = EmailOTP.objects.filter(email=email, purpose=EmailOTP.PURPOSE_REGISTER_VERIFY).order_by("-created_at").first()
        if last_otp:
            cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
            if (now - last_otp.last_sent_at).total_seconds() < cooldown:
                raise serializers.ValidationError({"detail": f"Please wait {cooldown} seconds before requesting OTP again."})

        hourly_count = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            created_at__gte=one_hour_ago
        ).count()
        max_per_hour = getattr(settings, "OTP_MAX_SEND_PER_HOUR", 5)
        if hourly_count >= max_per_hour:
            raise serializers.ValidationError({"detail": "OTP limit reached. Try again later."})

        otp = _generate_otp()
        salt = secrets.token_hex(8)
        otp_hash = _hash_otp(otp, salt)

        expires_min = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
        expires_at = now + timedelta(minutes=expires_min)

        EmailOTP.objects.create(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            otp_hash=otp_hash,
            salt=salt,
            expires_at=expires_at,
            is_used=False
        )

        subject = "Your Attendance App OTP (Resend)"
        message = (
            f"Your OTP is: {otp}\n\n"
            f"This OTP will expire in {expires_min} minutes.\n"
            f"If you did not request this, please ignore this email."
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)

        return attrs


class MeSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "is_verified", "is_active", "phone", "employee_code", "department", "designation"]

    def get_phone(self, obj):
        return getattr(getattr(obj, "profile", None), "phone", "")

    def get_employee_code(self, obj):
        return getattr(getattr(obj, "profile", None), "employee_code", "")

    def get_department(self, obj):
        return getattr(getattr(obj, "profile", None), "department", "")

    def get_designation(self, obj):
        return getattr(getattr(obj, "profile", None), "designation", "")
