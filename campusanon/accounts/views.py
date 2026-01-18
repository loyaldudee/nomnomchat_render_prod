from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, EmailOTP
from .utils import send_email_otp, hash_email, generate_internal_username

# ✅ Community Helpers
from communities.utils import (
    get_or_create_global_community,
    get_or_create_academic_community,
    add_user_to_community,
)

COLLEGE_DOMAIN = "@aitpune.edu.in"

class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Get email safely
        raw_email = request.data.get("email")
        
        if not raw_email:
             return Response({"error": "Email is required"}, status=400)

        # 2. Normalize (lowercase + remove spaces)
        email = raw_email.strip().lower()

        # 3. Domain Check
        if not email.endswith(COLLEGE_DOMAIN):
            return Response(
                {"error": "Access restricted. Only @aitpune.edu.in emails are allowed."}, 
                status=403
            )

        # 4. Send OTP
        try:
            send_email_otp(email)
            return Response({"message": "OTP sent successfully"})
        except Exception as e:
            print(f"Error sending OTP: {e}")
            return Response({"error": "Failed to send email"}, status=500)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Get and normalize data
        raw_email = request.data.get("email")
        otp = request.data.get("otp")
        year = request.data.get("year")
        branch = request.data.get("branch")

        if not raw_email or not otp:
            return Response({"error": "Email and OTP are required"}, status=400)

        email = raw_email.strip().lower()

        # 2. Verify OTP Record
        record = EmailOTP.objects.filter(email=email).first()

        if not record:
            return Response({"error": "No OTP found for this email"}, status=400)

        if record.is_expired():
            return Response({"error": "OTP has expired"}, status=400)

        if record.attempts >= 3:
            record.delete()  # Security: Clear it so they must request a new one
            return Response({"error": "Too many failed attempts. Request a new OTP."}, status=400)

        if record.otp != otp:
            record.attempts += 1
            record.save()
            return Response({"error": "Invalid OTP"}, status=400)

        # 3. OTP is valid! Create or Get User
        email_hash = hash_email(email)

        # Ensure year/branch are present for NEW users
        if not year or not branch:
            # We allow login without them if user exists, but need them for creation
            if not User.objects.filter(email_hash=email_hash).exists():
                 return Response({"error": "Year and Branch are required for registration"}, status=400)

        user, created = User.objects.get_or_create(
            email_hash=email_hash,
            defaults={
                "year": int(year) if year else 1,
                "branch": branch if branch else "General",
                "internal_username": generate_internal_username(),
            },
        )

        if user.is_banned:
            return Response({"error": "This account has been banned."}, status=403)

        # 4. Auto-Join Communities (Crucial Step)
        # We run this every login to ensure they are always in the right groups
        try:
            global_comm = get_or_create_global_community()
            add_user_to_community(user, global_comm)

            # If user has year/branch set, add to academic group
            if user.year and user.branch:
                academic_comm = get_or_create_academic_community(user.year, user.branch)
                add_user_to_community(user, academic_comm)
        except Exception as e:
            print(f"Error adding to community: {e}")
            # Don't fail login just because community add failed

        # 5. Generate Tokens
        refresh = RefreshToken.for_user(user)
        
        # Cleanup
        record.delete()

        return Response({
            "message": "Login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user.id),
            "username": user.internal_username,
            "is_new_user": created
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