import random
import hashlib
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from .models import EmailOTP
import string




def generate_internal_username():
    return "user_" + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=8)
    )

def generate_otp():
    return str(random.randint(100000, 999999))


def hash_email(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()


def send_email_otp(email):
    otp = generate_otp()

    EmailOTP.objects.update_or_create(
        email=email,
        defaults={
            "otp": otp,
            "expires_at": timezone.now() + timedelta(minutes=5),
            "attempts": 0,
        }
    )

    send_mail(
        subject="Your Verification Code",
        message=f"Your OTP is {otp}. It expires in 5 minutes.",
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )
