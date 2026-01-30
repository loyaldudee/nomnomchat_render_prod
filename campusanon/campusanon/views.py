from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class HealthCheckView(APIView):
    # ✅ AllowAny: Essential so UptimeRobot can ping it without a token
    permission_classes = [AllowAny]

    def get(self, request):
        # ⚡ Returns instantly. No DB query. No auth check.
        return Response({"status": "ok", "message": "I am awake! 🚀"})