import random
from datetime import timedelta
from django.utils import timezone
from .models import RateLimit
from campusanon.redis import redis_client
from .models import AdminAuditLog


def is_rate_limited(user, action, limit, window_seconds):
    window_start = timezone.now() - timedelta(seconds=window_seconds)

    count = RateLimit.objects.filter(
        user=user,
        action=action,
        created_at__gte=window_start
    ).count()

    if count >= limit:
        return True

    RateLimit.objects.create(user=user, action=action)
    return False

def is_rate_limited_redis(user_id, action, limit, window_seconds):
    """
    Redis-based fixed window rate limiter
    """
    key = f"rate:{action}:{user_id}"

    current = redis_client.get(key)

    if current is None:
        # First action in window
        redis_client.setex(key, window_seconds, 1)
        return False

    if int(current) >= limit:
        return True

    redis_client.incr(key)
    return False


def log_admin_action(admin, action, target_id, target_type, reason=""):
    AdminAuditLog.objects.create(
        admin=admin,
        action=action,
        target_id=target_id,
        target_type=target_type,
        reason=reason
    )


ADJECTIVES = [
    "Bhadkila", "Chulbula", "Pagal", "Chaman", "Pookie", "Chalu", "Kadwa", "Lafanga", "Jhootha", "Bhondu", "Chikna", "Maal", "Kaalu", "Sexy"
]

NOUNS = [
    "Aloo", "Tatta", "Bandar", "Qtiya", "Genda", "Napunsak", "Billu", "Chomu", "Chindi", "Nigger", "Susu", "Adrak", "Hottie", "Pucchi"
]


def generate_alias():
    return f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}{random.randint(100,999)}"
