from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, EmailOTP
from .utils import send_email_otp, hash_email, generate_internal_username


COLLEGE_DOMAIN = "@aitpune.edu.in"  


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email or not email.endswith("@aitpune.edu.in"):
            return Response(
                {"error": "Invalid college email"},
                status=400
            )

        send_email_otp(email)
        return Response({"message": "OTP sent"})


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        year = request.data.get("year")
        branch = request.data.get("branch")

        record = EmailOTP.objects.filter(email=email).first()

        if not record:
            return Response({"error": "OTP not found"}, status=400)

        if record.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        if record.attempts >= 3:
            return Response({"error": "Too many attempts"}, status=400)

        if record.otp != otp:
            record.attempts += 1
            record.save()
            return Response({"error": "Invalid OTP"}, status=400)

        email_hash = hash_email(email)

        user, created = User.objects.get_or_create(
            email_hash=email_hash,
            defaults={
                "year": year,
                "branch": branch,
                "internal_username": generate_internal_username(),
            },
        )

        if user.is_banned:
            return Response({"error": "User banned"}, status=403)

        refresh = RefreshToken.for_user(user)

        record.delete()

        return Response({
            "message": "Verified",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "user_id": str(request.user.id),
            "internal_username": request.user.internal_username,
            "year": request.user.year,
            "branch": request.user.branch
        })
