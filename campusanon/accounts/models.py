import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Disable default username/email (we use OTP)
    username = None
    email = None

    email_hash = models.CharField(max_length=64, unique=True)

    internal_username = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )

    year = models.IntegerField()
    branch = models.CharField(max_length=50)
    is_banned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email_hash"
    REQUIRED_FIELDS = []

    def __str__(self):
        return str(self.id)


class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.expires_at
