from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, EmailOTP
from .utils import send_email_otp, hash_email, generate_internal_username

# ✅ Import Community Models directly for strict lookup
from communities.models import Community, CommunityMembership

COLLEGE_DOMAIN = "@aitpune.edu.in"

class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_email = request.data.get("email")
        if not raw_email:
             return Response({"error": "Email is required"}, status=400)

        email = raw_email.strip().lower()

        if not email.endswith(COLLEGE_DOMAIN):
            return Response(
                {"error": "Access restricted. Only @aitpune.edu.in emails are allowed."}, 
                status=403
            )

        try:
            send_email_otp(email)
            return Response({"message": "OTP sent successfully"})
        except Exception as e:
            print(f"Error sending OTP: {e}")
            return Response({"error": "Failed to send email"}, status=500)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Get Data
        raw_email = request.data.get("email")
        otp = request.data.get("otp")
        
        # New Registration Fields
        year = request.data.get("year")
        branch = request.data.get("branch")     # e.g. "Computer" or "COMP"
        division = request.data.get("division") # e.g. "A", "B", or ""/None

        if not raw_email or not otp:
            return Response({"error": "Email and OTP are required"}, status=400)

        email = raw_email.strip().lower()

        # 2. Verify OTP Logic (Standard)
        record = EmailOTP.objects.filter(email=email).first()
        if not record:
            return Response({"error": "No OTP found"}, status=400)
        if record.is_expired():
            return Response({"error": "OTP has expired"}, status=400)
        if record.attempts >= 3:
            record.delete()
            return Response({"error": "Too many failed attempts."}, status=400)
        if record.otp != otp:
            record.attempts += 1
            record.save()
            return Response({"error": "Invalid OTP"}, status=400)

        # 3. OTP is Valid! Handle User.
        email_hash = hash_email(email)
        user_exists = User.objects.filter(email_hash=email_hash).exists()

        if not user_exists:
            # Registration: Year & Branch are MANDATORY
            if not year or not branch:
                 return Response({"error": "Year and Branch are required for new users"}, status=400)
            
            # Map Full Names to Short Codes (if frontend sends full names)
            BRANCH_MAP = {
                "Computer": "COMP",
                "Information Technology": "IT",
                "E&TC": "ENTC",
                "ENTC": "ENTC",
                "Mechanical": "MECH",
                "ASGE": "ARE", # Automation & Robotics
                "ARE": "ARE"
            }
            clean_branch = BRANCH_MAP.get(branch, branch) # Fallback to input if not in map

            # Normalize Division (ensure it's None if empty string)
            clean_div = division if division in ['A', 'B'] else None

            # 🛑 CRITICAL: Check if Community Exists BEFORE Creating User
            # We don't want to create a user if they selected an invalid community
            try:
                target_community = Community.objects.get(
                    year=year,
                    branch=clean_branch,
                    division=clean_div
                )
            except Community.DoesNotExist:
                return Response(
                    {"error": f"Invalid Class: {year} {clean_branch} {clean_div or ''} does not exist."},
                    status=400
                )

            # Create User
            user = User.objects.create(
                email_hash=email_hash,
                year=int(year),
                branch=clean_branch,
                # We can store division in user model if you want, but community membership is enough
                internal_username=generate_internal_username()
            )

            # ✅ Add to the STRICT Community
            CommunityMembership.objects.create(user=user, community=target_community)
            
            # ✅ Add to Global Community (Safe lookup)
            global_comm = Community.objects.filter(is_global=True).first()
            if global_comm:
                CommunityMembership.objects.get_or_create(user=user, community=global_comm)

            is_new_user = True

        else:
            # Login: Just get the user
            user = User.objects.get(email_hash=email_hash)
            if user.is_banned:
                return Response({"error": "This account has been banned."}, status=403)
            is_new_user = False

        # 4. Generate Tokens
        refresh = RefreshToken.for_user(user)
        record.delete() # Cleanup OTP

        return Response({
            "message": "Login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user.id),
            "username": user.internal_username,
            "is_new_user": is_new_user
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