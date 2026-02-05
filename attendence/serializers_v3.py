# attendence/serializers.py

import hashlib
import secrets
import math
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import localdate
from rest_framework import serializers

from .models import (
    User,
    EmployeeProfile,
    EmailOTP,

    OfficeLocation,
    OfficeQR,
    Attendance,

    LeaveRequest,
    RegularizationRequest,
    ResignationRequest,

    EmployeeDocument,
    ESICProfile,
    OfflineAttendanceRequest,

    RosterShift,
    RosterAssignment,

    DailyReport,
)


# ============================================================
# OTP HELPERS + SAFE EMAIL SEND (FIXED)
# ============================================================
def _hash_otp(otp: str, salt: str) -> str:
    return hashlib.sha256(f"{otp}:{salt}".encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _safe_last_sent_at(obj):
    """
    Some projects have EmailOTP.last_sent_at, some don't.
    If missing/None, fallback to created_at.
    """
    v = getattr(obj, "last_sent_at", None)
    if v:
        return v
    return getattr(obj, "created_at", None)


def send_otp_email(to_email: str, subject: str, message: str):
    """
    Robust SMTP send:
    - Explicit open()
    - Clean ValidationError (no raw 500 SMTPServerDisconnected)
    """
    try:
        conn = get_connection(fail_silently=False)
        opened = conn.open()
        if not opened:
            raise serializers.ValidationError({"detail": "SMTP connection could not be opened."})

        try:
            EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
                connection=conn,
            ).send(fail_silently=False)
        finally:
            conn.close()

    except Exception as e:
        raise serializers.ValidationError({"detail": f"Failed to send OTP email. SMTP error: {str(e)}"})


# ============================================================
# AUTH SERIALIZERS
# ============================================================
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
        full_name = (validated_data.get("full_name") or "").strip()
        phone = (validated_data.get("phone") or "").strip()

        existing = User.objects.filter(email=email).first()
        if existing and existing.is_verified:
            raise serializers.ValidationError({"email": "User already exists and verified. Please login."})

        # Re-register not verified user
        if existing and not existing.is_verified:
            user = existing
            if full_name:
                user.full_name = full_name
            user.set_password(password)
            user.is_active = False
            user.is_verified = False
            user.save()
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                is_active=False,
                is_verified=False,
            )

        # Ensure profile exists
        EmployeeProfile.objects.get_or_create(user=user, defaults={"phone": phone})
        if phone:
            profile = user.profile
            profile.phone = phone
            profile.save()

        # OTP throttle: cooldown + per hour limit
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)

        last_otp = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY
        ).order_by("-created_at").first()

        if last_otp:
            cooldown = int(getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60) or 60)
            last_sent = _safe_last_sent_at(last_otp)
            if last_sent and (now - last_sent).total_seconds() < cooldown:
                wait = cooldown - int((now - last_sent).total_seconds())
                raise serializers.ValidationError({"detail": f"Please wait {max(wait,1)} seconds before requesting OTP again."})

            hourly_count = EmailOTP.objects.filter(
                email=email,
                purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
                created_at__gte=one_hour_ago,
            ).count()
            max_per_hour = int(getattr(settings, "OTP_MAX_SEND_PER_HOUR", 5) or 5)
            if hourly_count >= max_per_hour:
                raise serializers.ValidationError({"detail": "OTP limit reached. Try again later."})

        otp = _generate_otp()
        salt = secrets.token_hex(8)
        otp_hash = _hash_otp(otp, salt)

        expires_min = int(getattr(settings, "OTP_EXPIRY_MINUTES", 10) or 10)
        expires_at = now + timedelta(minutes=expires_min)

        otp_obj = EmailOTP.objects.create(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            otp_hash=otp_hash,
            salt=salt,
            expires_at=expires_at,
            is_used=False,
        )

        # if model has last_sent_at, save it
        if hasattr(otp_obj, "last_sent_at"):
            otp_obj.last_sent_at = now
            otp_obj.save(update_fields=["last_sent_at"])

        subject = "Your Attendance App OTP"
        message = (
            f"Your OTP is: {otp}\n\n"
            f"This OTP will expire in {expires_min} minutes.\n"
            f"If you did not request this, please ignore this email."
        )

        # ✅ Send after DB commit (CRITICAL FIX)
        transaction.on_commit(lambda: send_otp_email(email, subject, message))

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

        user.is_verified = True
        user.is_active = True
        user.save(update_fields=["is_verified", "is_active"])

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

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

        last_otp = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY
        ).order_by("-created_at").first()

        if last_otp:
            cooldown = int(getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60) or 60)
            last_sent = _safe_last_sent_at(last_otp)
            if last_sent and (now - last_sent).total_seconds() < cooldown:
                wait = cooldown - int((now - last_sent).total_seconds())
                raise serializers.ValidationError({"detail": f"Please wait {max(wait,1)} seconds before requesting OTP again."})

        hourly_count = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            created_at__gte=one_hour_ago
        ).count()
        max_per_hour = int(getattr(settings, "OTP_MAX_SEND_PER_HOUR", 5) or 5)
        if hourly_count >= max_per_hour:
            raise serializers.ValidationError({"detail": "OTP limit reached. Try again later."})

        otp = _generate_otp()
        salt = secrets.token_hex(8)
        otp_hash = _hash_otp(otp, salt)

        expires_min = int(getattr(settings, "OTP_EXPIRY_MINUTES", 10) or 10)
        expires_at = now + timedelta(minutes=expires_min)

        otp_obj = EmailOTP.objects.create(
            email=email,
            purpose=EmailOTP.PURPOSE_REGISTER_VERIFY,
            otp_hash=otp_hash,
            salt=salt,
            expires_at=expires_at,
            is_used=False
        )

        if hasattr(otp_obj, "last_sent_at"):
            otp_obj.last_sent_at = now
            otp_obj.save(update_fields=["last_sent_at"])

        subject = "Your Attendance App OTP (Resend)"
        message = (
            f"Your OTP is: {otp}\n\n"
            f"This OTP will expire in {expires_min} minutes.\n"
            f"If you did not request this, please ignore this email."
        )

        # ✅ Send after commit
        transaction.on_commit(lambda: send_otp_email(email, subject, message))

        return attrs


class MeSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "is_verified", "is_active",
            "phone", "employee_code", "department", "designation",
            "is_staff", "is_superuser"
        ]

    def get_phone(self, obj):
        return getattr(getattr(obj, "profile", None), "phone", "")

    def get_employee_code(self, obj):
        return getattr(getattr(obj, "profile", None), "employee_code", "")

    def get_department(self, obj):
        return getattr(getattr(obj, "profile", None), "department", "")

    def get_designation(self, obj):
        return getattr(getattr(obj, "profile", None), "designation", "")


# ============================================================
# ATTENDANCE SERIALIZERS
# ============================================================
def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class AttendanceMarkSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["CHECKIN", "CHECKOUT"])
    qr_token = serializers.CharField(max_length=80)
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    accuracy_m = serializers.FloatField(required=False)

    def validate(self, attrs):
        user = self.context["request"].user

        if not user.is_verified:
            raise serializers.ValidationError({"detail": "Email not verified."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account inactive."})

        qr_token = attrs["qr_token"].strip()
        qr = OfficeQR.objects.select_related("office").filter(
            qr_token=qr_token, is_active=True, office__is_active=True
        ).first()
        if not qr:
            raise serializers.ValidationError({"qr_token": "Invalid or inactive QR."})

        office = qr.office
        dist_m = haversine_m(attrs["lat"], attrs["lng"], office.latitude, office.longitude)
        if dist_m > office.allowed_radius_m:
            raise serializers.ValidationError({
                "detail": f"Outside allowed location radius. Distance={int(dist_m)}m, Allowed={office.allowed_radius_m}m"
            })

        attrs["office"] = office
        attrs["distance_m"] = dist_m
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        office = validated_data["office"]
        action = validated_data["action"]
        lat = validated_data["lat"]
        lng = validated_data["lng"]
        accuracy_m = validated_data.get("accuracy_m", None)

        today = localdate()
        attendance = Attendance.objects.select_for_update().filter(user=user, date=today).first()
        now = timezone.now()

        if action == "CHECKIN":
            if attendance and attendance.check_in_time:
                return {"status": "ALREADY_CHECKED_IN", "attendance_id": attendance.id}

            if not attendance:
                attendance = Attendance.objects.create(
                    user=user,
                    office=office,
                    date=today,
                    check_in_time=now,
                    check_in_lat=lat,
                    check_in_lng=lng,
                    check_in_accuracy_m=accuracy_m,
                    source=Attendance.SOURCE_ONLINE,
                )
            else:
                attendance.office = office
                attendance.check_in_time = now
                attendance.check_in_lat = lat
                attendance.check_in_lng = lng
                attendance.check_in_accuracy_m = accuracy_m
                attendance.save()

            return {"status": "CHECKED_IN", "attendance_id": attendance.id}

        # CHECKOUT
        if not attendance or not attendance.check_in_time:
            raise serializers.ValidationError({"detail": "You must CHECKIN first."})

        if attendance.check_out_time:
            return {"status": "ALREADY_CHECKED_OUT", "attendance_id": attendance.id}

        attendance.check_out_time = now
        attendance.check_out_lat = lat
        attendance.check_out_lng = lng
        attendance.check_out_accuracy_m = accuracy_m
        attendance.save()

        return {"status": "CHECKED_OUT", "attendance_id": attendance.id}


class AttendanceListSerializer(serializers.ModelSerializer):
    office_name = serializers.CharField(source="office.name", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id", "date", "office_name",
            "check_in_time", "check_out_time",
            "check_in_lat", "check_in_lng",
            "check_out_lat", "check_out_lng",
            "source",
        ]


class OfficeLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeLocation
        fields = ["id", "name", "address", "latitude", "longitude", "allowed_radius_m", "is_active", "created_at"]


class OfficeQRSerializer(serializers.ModelSerializer):
    office_name = serializers.CharField(source="office.name", read_only=True)

    class Meta:
        model = OfficeQR
        fields = ["id", "office", "office_name", "qr_token", "is_active", "created_at"]


# ============================================================
# LEAVE / REGULARIZATION / RESIGNATION
# ============================================================
class LeaveRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = ["user", "status", "admin_comment", "decided_by", "decided_at", "created_at"]

    def validate(self, attrs):
        if attrs["to_date"] < attrs["from_date"]:
            raise serializers.ValidationError({"to_date": "To date must be >= From date"})
        return attrs

    def create(self, validated_data):
        return LeaveRequest.objects.create(user=self.context["request"].user, **validated_data)


class AdminLeaveDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[LeaveRequest.STATUS_APPROVED, LeaveRequest.STATUS_REJECTED])
    admin_comment = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance: LeaveRequest, validated_data):
        instance.status = validated_data["status"]
        instance.admin_comment = validated_data.get("admin_comment", "")
        instance.decided_by = self.context["request"].user
        instance.decided_at = timezone.now()
        instance.save()
        return instance


class RegularizationRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = RegularizationRequest
        fields = "__all__"
        read_only_fields = ["user", "status", "admin_comment", "decided_by", "decided_at", "created_at"]

    def create(self, validated_data):
        return RegularizationRequest.objects.create(user=self.context["request"].user, **validated_data)


class AdminRegularizationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[RegularizationRequest.STATUS_APPROVED, RegularizationRequest.STATUS_REJECTED])
    admin_comment = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance: RegularizationRequest, validated_data):
        instance.status = validated_data["status"]
        instance.admin_comment = validated_data.get("admin_comment", "")
        instance.decided_by = self.context["request"].user
        instance.decided_at = timezone.now()
        instance.save()
        return instance


class ResignationRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = ResignationRequest
        fields = "__all__"
        read_only_fields = ["user", "status", "admin_comment", "decided_by", "decided_at", "created_at"]

    def create(self, validated_data):
        return ResignationRequest.objects.create(user=self.context["request"].user, **validated_data)


class AdminResignationDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[ResignationRequest.STATUS_APPROVED, ResignationRequest.STATUS_REJECTED])
    admin_comment = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance: ResignationRequest, validated_data):
        instance.status = validated_data["status"]
        instance.admin_comment = validated_data.get("admin_comment", "")
        instance.decided_by = self.context["request"].user
        instance.decided_at = timezone.now()
        instance.save()
        return instance


# ============================================================
# DOCUMENTS / ESIC
# ============================================================
class EmployeeDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = ["id", "doc_type", "title", "file", "file_url", "uploaded_at"]
        read_only_fields = ["id", "file_url", "uploaded_at"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return ""

    def create(self, validated_data):
        return EmployeeDocument.objects.create(user=self.context["request"].user, **validated_data)


class ESICProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ESICProfile
        fields = ["esic_number", "dispensary", "branch_office", "updated_at"]
        read_only_fields = ["updated_at"]


# ============================================================
# OFFLINE ATTENDANCE REQUEST
# ============================================================
class OfflineAttendanceRequestSerializer(serializers.ModelSerializer):
    office_name = serializers.CharField(source="office.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = OfflineAttendanceRequest
        fields = "__all__"
        read_only_fields = [
            "user", "status", "admin_comment", "decided_by", "decided_at", "created_at", "office_name"
        ]

    def create(self, validated_data):
        return OfflineAttendanceRequest.objects.create(user=self.context["request"].user, **validated_data)


class AdminOfflineDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[OfflineAttendanceRequest.STATUS_APPROVED, OfflineAttendanceRequest.STATUS_REJECTED])
    admin_comment = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance: OfflineAttendanceRequest, validated_data):
        instance.status = validated_data["status"]
        instance.admin_comment = validated_data.get("admin_comment", "")
        instance.decided_by = self.context["request"].user
        instance.decided_at = timezone.now()
        instance.save()

        # If approved => create/update Attendance
        if instance.status == OfflineAttendanceRequest.STATUS_APPROVED:
            att, _ = Attendance.objects.get_or_create(
                user=instance.user,
                date=instance.date,
                defaults={"office": instance.office},
            )
            att.office = instance.office
            if instance.check_in_time:
                att.check_in_time = instance.check_in_time
            if instance.check_out_time:
                att.check_out_time = instance.check_out_time
            att.source = Attendance.SOURCE_OFFLINE
            att.save()

        return instance


# ============================================================
# ROSTER
# ============================================================
class RosterShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = RosterShift
        fields = "__all__"


class RosterAssignmentSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source="shift.name", read_only=True)
    office_name = serializers.CharField(source="office.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = RosterAssignment
        fields = ["id", "user", "office", "office_name", "date", "shift", "shift_name", "note", "created_at"]
        read_only_fields = ["id", "created_at", "shift_name", "office_name"]


# ============================================================
# ADMIN USER LIST
# ============================================================
class AdminUserListSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    employee_code = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name",
            "phone", "employee_code", "department", "designation",
            "is_active", "is_verified", "is_staff", "is_superuser",
        ]

    def get_phone(self, obj):
        return getattr(getattr(obj, "profile", None), "phone", "")

    def get_employee_code(self, obj):
        return getattr(getattr(obj, "profile", None), "employee_code", "")

    def get_department(self, obj):
        return getattr(getattr(obj, "profile", None), "department", "")

    def get_designation(self, obj):
        return getattr(getattr(obj, "profile", None), "designation", "")


# ============================================================
# DAILY REPORTS
# ============================================================
class DailyReportSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = DailyReport
        fields = [
            "id",
            "user", "user_email", "user_name",
            "report_date",
            "title",
            "description",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "user_email", "user_name", "created_at", "updated_at"]

    def create(self, validated_data):
        return DailyReport.objects.create(user=self.context["request"].user, **validated_data)
