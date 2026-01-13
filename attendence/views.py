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
