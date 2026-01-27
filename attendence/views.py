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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils.timezone import localdate

from .models import (
    LeaveRequest, RegularizationRequest, ResignationRequest,
    EmployeeDocument, ESICProfile, OfflineAttendanceRequest,
    RosterShift, RosterAssignment, OfficeLocation
)
from .serializers import (
    LeaveRequestSerializer, AdminLeaveDecisionSerializer,
    RegularizationRequestSerializer, AdminRegularizationDecisionSerializer,
    ResignationRequestSerializer, AdminResignationDecisionSerializer,
    EmployeeDocumentSerializer, ESICProfileSerializer,
    OfflineAttendanceRequestSerializer, AdminOfflineDecisionSerializer,
    RosterShiftSerializer, RosterAssignmentSerializer
)

# ---------------------------
# Leaves
# ---------------------------
class MyLeaveListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = LeaveRequest.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(LeaveRequestSerializer(qs, many=True).data)

    def post(self, request):
        ser = LeaveRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(LeaveRequestSerializer(obj).data, status=201)


class AdminLeaveListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_q = request.query_params.get("status")  # optional
        qs = LeaveRequest.objects.all().order_by("-created_at")
        if status_q:
            qs = qs.filter(status=status_q)
        return Response(LeaveRequestSerializer(qs, many=True).data)


class AdminLeaveDecideView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, leave_id: int):
        obj = LeaveRequest.objects.filter(id=leave_id).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        ser = AdminLeaveDecisionSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.update(obj, ser.validated_data)
        return Response(LeaveRequestSerializer(obj).data, status=200)


# ---------------------------
# Regularization
# ---------------------------
class MyRegularizationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = RegularizationRequest.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(RegularizationRequestSerializer(qs, many=True).data)

    def post(self, request):
        ser = RegularizationRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(RegularizationRequestSerializer(obj).data, status=201)


class AdminRegularizationListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_q = request.query_params.get("status")
        qs = RegularizationRequest.objects.all().order_by("-created_at")
        if status_q:
            qs = qs.filter(status=status_q)
        return Response(RegularizationRequestSerializer(qs, many=True).data)


class AdminRegularizationDecideView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, req_id: int):
        obj = RegularizationRequest.objects.filter(id=req_id).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        ser = AdminRegularizationDecisionSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.update(obj, ser.validated_data)
        return Response(RegularizationRequestSerializer(obj).data, status=200)


# ---------------------------
# Resignation
# ---------------------------
class MyResignationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ResignationRequest.objects.filter(user=request.user).order_by("-created_at")[:100]
        return Response(ResignationRequestSerializer(qs, many=True).data)

    def post(self, request):
        ser = ResignationRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(ResignationRequestSerializer(obj).data, status=201)


class AdminResignationListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_q = request.query_params.get("status")
        qs = ResignationRequest.objects.all().order_by("-created_at")
        if status_q:
            qs = qs.filter(status=status_q)
        return Response(ResignationRequestSerializer(qs, many=True).data)


class AdminResignationDecideView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, req_id: int):
        obj = ResignationRequest.objects.filter(id=req_id).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        ser = AdminResignationDecisionSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.update(obj, ser.validated_data)
        return Response(ResignationRequestSerializer(obj).data, status=200)


# ---------------------------
# Documents
# ---------------------------
class MyDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = EmployeeDocument.objects.filter(user=request.user).order_by("-uploaded_at")[:200]
        return Response(EmployeeDocumentSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        # multipart/form-data expected
        ser = EmployeeDocumentSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(EmployeeDocumentSerializer(obj, context={"request": request}).data, status=201)


class MyDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, doc_id: int):
        obj = EmployeeDocument.objects.filter(id=doc_id, user=request.user).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        obj.file.delete(save=False)
        obj.delete()
        return Response({"detail": "Deleted"}, status=200)


# ---------------------------
# ESIC
# ---------------------------
class MyESICView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        obj, _ = ESICProfile.objects.get_or_create(user=request.user)
        return Response(ESICProfileSerializer(obj).data, status=200)

    def patch(self, request):
        obj, _ = ESICProfile.objects.get_or_create(user=request.user)
        ser = ESICProfileSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ESICProfileSerializer(obj).data, status=200)


# ---------------------------
# Offline Attendance Request
# ---------------------------
class MyOfflineAttendanceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OfflineAttendanceRequest.objects.filter(user=request.user).select_related("office").order_by("-created_at")[:100]
        return Response(OfflineAttendanceRequestSerializer(qs, many=True).data)

    def post(self, request):
        ser = OfflineAttendanceRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(OfflineAttendanceRequestSerializer(obj).data, status=201)


class AdminOfflineAttendanceListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_q = request.query_params.get("status")
        qs = OfflineAttendanceRequest.objects.select_related("office", "user").order_by("-created_at")
        if status_q:
            qs = qs.filter(status=status_q)
        return Response(OfflineAttendanceRequestSerializer(qs, many=True).data)


class AdminOfflineAttendanceDecideView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, req_id: int):
        obj = OfflineAttendanceRequest.objects.filter(id=req_id).first()
        if not obj:
            return Response({"detail": "Not found"}, status=404)
        ser = AdminOfflineDecisionSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.update(obj, ser.validated_data)
        return Response(OfflineAttendanceRequestSerializer(obj).data, status=200)


# ---------------------------
# Roster
# ---------------------------
class MyRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # /api/roster/me/?from=YYYY-MM-DD&to=YYYY-MM-DD
        qs = RosterAssignment.objects.filter(user=request.user).select_related("shift", "office").order_by("-date")

        from_date = request.query_params.get("from")
        to_date = request.query_params.get("to")
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        if not from_date and not to_date:
            qs = qs[:30]

        return Response(RosterAssignmentSerializer(qs, many=True).data, status=200)


class AdminShiftListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = RosterShift.objects.all().order_by("name")
        return Response(RosterShiftSerializer(qs, many=True).data)

    def post(self, request):
        ser = RosterShiftSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(RosterShiftSerializer(obj).data, status=201)


class AdminRosterAssignView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        """
        Body:
        {
          "user": 12,
          "office": 1,
          "date": "2026-01-26",
          "shift": 2,
          "note": "optional"
        }
        """
        ser = RosterAssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        data = ser.validated_data
        obj, _ = RosterAssignment.objects.update_or_create(
            user=data["user"],
            date=data["date"],
            defaults={
                "office": data["office"],
                "shift": data["shift"],
                "note": data.get("note", ""),
            }
        )
        return Response(RosterAssignmentSerializer(obj).data, status=200)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from .models import User
from .serializers import AdminUserListSerializer

class AdminUserListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        qs = User.objects.all().order_by("-id")

        if q:
            qs = qs.filter(email__icontains=q) | qs.filter(full_name__icontains=q)

        return Response(AdminUserListSerializer(qs, many=True).data)
