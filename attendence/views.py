from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import (
    RegisterSerializer,
    VerifyOtpSerializer,
    ResendOtpSerializer,
    MeSerializer,
)
from .models import User


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(
            {"detail": "Registered successfully. OTP has been sent to your email."},
            status=status.HTTP_201_CREATED
        )


class VerifyOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = VerifyOtpSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response({"detail": "OTP verified successfully. You can login now."}, status=status.HTTP_200_OK)


class ResendOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = ResendOtpSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response({"detail": "OTP resent successfully."}, status=status.HTTP_200_OK)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Email + password login
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name or ""
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if not user.is_verified:
            # verified nahi hai to login deny
            raise permissions.PermissionDenied("Email not verified. Please verify OTP first.")

        if not user.is_active:
            raise permissions.PermissionDenied("Account inactive. Please contact admin.")

        return data


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data, status=status.HTTP_200_OK)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import localdate
from datetime import datetime

from .serializers import AttendanceMarkSerializer, AttendanceListSerializer
from .models import Attendance


class AttendanceMarkView(APIView):
    """
    POST /api/attendance/mark/
    Body:
    {
      "action": "CHECKIN" or "CHECKOUT",
      "qr_token": "scanned-token",
      "lat": 28.61,
      "lng": 77.20,
      "accuracy_m": 15
    }
    """
    def post(self, request):
        ser = AttendanceMarkSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        result = ser.save()
        return Response(result, status=status.HTTP_200_OK)


class MyAttendanceListView(APIView):
    """
    GET /api/attendance/me/?from=2026-01-01&to=2026-01-31
    If no dates: last 30 records default
    """
    def get(self, request):
        qs = Attendance.objects.filter(user=request.user).select_related("office").order_by("-date")

        from_date = request.query_params.get("from")
        to_date = request.query_params.get("to")

        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        # default limit
        if not from_date and not to_date:
            qs = qs[:30]

        data = AttendanceListSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class TodayAttendanceStatusView(APIView):
    """
    GET /api/attendance/today/
    """
    def get(self, request):
        today = localdate()
        att = Attendance.objects.filter(user=request.user, date=today).select_related("office").first()
        if not att:
            return Response({"date": str(today), "checked_in": False, "checked_out": False}, status=status.HTTP_200_OK)

        return Response({
            "date": str(today),
            "office": att.office.name,
            "checked_in": bool(att.check_in_time),
            "checked_out": bool(att.check_out_time),
            "check_in_time": att.check_in_time,
            "check_out_time": att.check_out_time,
        }, status=status.HTTP_200_OK)

import secrets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser

from .models import OfficeLocation, OfficeQR
from .serializers import OfficeLocationSerializer, OfficeQRSerializer


class AdminOfficeListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        offices = OfficeLocation.objects.all().order_by("-id")
        return Response(OfficeLocationSerializer(offices, many=True).data)

    def post(self, request):
        ser = OfficeLocationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        office = ser.save()
        return Response(OfficeLocationSerializer(office).data, status=status.HTTP_201_CREATED)


class AdminOfficeUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, office_id):
        office = OfficeLocation.objects.filter(id=office_id).first()
        if not office:
            return Response({"detail": "Office not found"}, status=404)

        ser = OfficeLocationSerializer(office, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        office = ser.save()
        return Response(OfficeLocationSerializer(office).data, status=200)


class AdminGenerateOfficeQRView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, office_id):
        office = OfficeLocation.objects.filter(id=office_id, is_active=True).first()
        if not office:
            return Response({"detail": "Office not found or inactive"}, status=404)

        token = secrets.token_urlsafe(24)  # ✅ strong unique token
        qr, created = OfficeQR.objects.get_or_create(
            office=office,
            defaults={"qr_token": token, "is_active": True},
        )
        if not created:
            qr.qr_token = token
            qr.is_active = True
            qr.save()

        return Response(OfficeQRSerializer(qr).data, status=200)


class AdminGetOfficeQRView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, office_id):
        qr = OfficeQR.objects.select_related("office").filter(office_id=office_id).first()
        if not qr:
            return Response({"detail": "QR not generated yet"}, status=404)
        return Response(OfficeQRSerializer(qr).data, status=200)
