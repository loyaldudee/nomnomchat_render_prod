from django.urls import path
from .views import SendOTPView, VerifyOTPView, MeView

urlpatterns = [
    path("send-otp/", SendOTPView.as_view()),
    path("verify-otp/", VerifyOTPView.as_view()),
    path("me/", MeView.as_view()),
]
