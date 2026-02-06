from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from .models import Community, CommunityMembership
from django.db.models import Count, Sum, F, IntegerField, Q
from django.db.models.functions import Coalesce
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
from campusanon.redis import redis_client

from .utils import get_or_create_global_community  # ✅ Import this helper

class MyCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. GENERATE A UNIQUE CACHE KEY
        # ⚠️ FIX: We added '_v2_' and '{user.id}' to the admin key.
        # This forces a fresh fetch and prevents admins from sharing stale data.
        cache_key = f"communities_v2_{user.id}"
        
        # 2. CHECK REDIS
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # ---------------------------------------------------------
        # 👑 GOD MODE (Staff/Superuser)
        # ---------------------------------------------------------
        if user.is_staff or user.is_superuser:
            print(f"👑 ADMIN DETECTED ({user.internal_username}): Checking Integrity...")
            
            # ✅ SELF-HEAL: If 'All' is missing for some reason, create it NOW.
            # This fixes the issue where CLI-created superusers don't trigger the setup script.
            if not Community.objects.filter(slug="all").exists():
                print("   🛠️ Self-Healing: Re-creating missing 'All' community...")
                get_or_create_global_community()

            # Admins see EVERYTHING
            all_communities = Community.objects.all()
        
        else:
            # -----------------------------------------------------
            # NORMAL STUDENT LOGIC (Strict Mode)
            # -----------------------------------------------------
            
            # 1. GLOBAL: Get 'All'
            auto_communities = Community.objects.filter(is_global=True)

            # 2. MANUAL: Get strictly joined communities
            joined_ids = CommunityMembership.objects.filter(
                user=user
            ).values_list('community_id', flat=True)
            
            manual_communities = Community.objects.filter(id__in=joined_ids)

            # 3. COMBINE
            all_communities = (auto_communities | manual_communities).distinct()

        # 4. Serialize
        data = []
        for c in all_communities:
            data.append({
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "is_global": c.is_global,
                "branch": c.branch, 
                "year": c.year,
                "division": c.division 
            })

        # 5. SAVE TO REDIS (15 mins)
        cache.set(cache_key, data, timeout=900)

        return Response(data)
    


class SearchCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_banned:
            return Response({"error": "User is banned"}, status=403)

        query = request.query_params.get("q", "").strip()
        if not query:
            return Response([])

        communities = Community.objects.filter(name__icontains=query)[:20]

        return Response([{
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "is_global": c.is_global
        } for c in communities])
    

class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ---------------------------------------------------------
        # 1. TIMEZONE AWARE LOGIC (IST +5:30)
        # ---------------------------------------------------------
        now_utc = timezone.now()
        
        ist_tz = ZoneInfo('Asia/Kolkata')
        now_ist = now_utc.astimezone(ist_tz)
        
        today_6am_ist = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)
        
        if now_ist < today_6am_ist:
            start_ist = today_6am_ist - timedelta(days=1)
        else:
            start_ist = today_6am_ist

        prev_start_ist = start_ist - timedelta(days=1)
        prev_end_ist = start_ist

        # ✅ FIX: Use dt_timezone.utc (Standard Python)
        current_start_utc = start_ist.astimezone(dt_timezone.utc)
        prev_start_utc = prev_start_ist.astimezone(dt_timezone.utc)
        prev_end_utc = prev_end_ist.astimezone(dt_timezone.utc)

        # ---------------------------------------------------------
        # 2. CACHE CHECK
        # ---------------------------------------------------------
        cache_key = f"leaderboard_ist_v1_{start_ist.strftime('%Y%m%d')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        response_data = {}

        # ---------------------------------------------------------
        # 3. GENERATE LEADERBOARD PER YEAR
        # ---------------------------------------------------------
        for year in [1, 2, 3, 4]:
            
            live_communities = Community.objects.filter(year=year, is_global=False).annotate(
                daily_posts=Count('post', filter=Q(post__created_at__gte=current_start_utc), distinct=True),
                daily_likes=Count('post__likes', filter=Q(post__likes__created_at__gte=current_start_utc), distinct=True),
                daily_comments=Count('post__comments', filter=Q(post__comments__created_at__gte=current_start_utc), distinct=True),
                daily_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__gte=current_start_utc), distinct=True)
            )

            leaderboard_list = []
            for c in live_communities:
                score = (
                    (c.daily_posts * 5) + 
                    (c.daily_likes * 2) + 
                    (c.daily_comments * 8) + 
                    (c.daily_comment_likes * 1)
                )
                leaderboard_list.append({
                    "id": str(c.id),
                    "name": c.name,
                    "branch": c.branch,
                    "division": c.division,
                    "score": score,
                    "stats": {
                        "posts": c.daily_posts,
                        "likes": c.daily_likes,
                        "comments": c.daily_comments
                    }
                })

            leaderboard_list.sort(key=lambda x: x['score'], reverse=True)
            
            for idx, item in enumerate(leaderboard_list):
                item['rank'] = idx + 1

            # B. GET YESTERDAY'S WINNER
            past_communities = Community.objects.filter(year=year, is_global=False).annotate(
                past_posts=Count('post', filter=Q(post__created_at__range=(prev_start_utc, prev_end_utc)), distinct=True),
                past_likes=Count('post__likes', filter=Q(post__likes__created_at__range=(prev_start_utc, prev_end_utc)), distinct=True),
                past_comments=Count('post__comments', filter=Q(post__comments__created_at__range=(prev_start_utc, prev_end_utc)), distinct=True),
                past_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__range=(prev_start_utc, prev_end_utc)), distinct=True)
            )
            
            winner_data = None
            highest_past_score = -1

            for c in past_communities:
                p_score = (
                    (c.past_posts * 5) + 
                    (c.past_likes * 2) + 
                    (c.past_comments * 8) + 
                    (c.past_comment_likes * 1)
                )
                if p_score > highest_past_score and p_score > 0:
                    highest_past_score = p_score
                    winner_data = {
                        "id": str(c.id),
                        "name": c.name,
                        "score": p_score,
                        "title": "Yesterday's Champion"
                    }

            response_data[year] = {
                "live_leaderboard": leaderboard_list,
                "yesterday_winner": winner_data
            }

        cache.set(cache_key, response_data, timeout=300)
        return Response(response_data)


class CommunityScoreView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        try:
            # 1. Calculate Time Window (IST)
            now_utc = timezone.now()
            ist_tz = ZoneInfo('Asia/Kolkata')
            now_ist = now_utc.astimezone(ist_tz)
            
            today_6am_ist = now_ist.replace(hour=6, minute=0, second=0, microsecond=0)
            
            if now_ist < today_6am_ist:
                start_ist = today_6am_ist - timedelta(days=1)
            else:
                start_ist = today_6am_ist
                
            # ✅ FIX: Use dt_timezone.utc
            current_start_utc = start_ist.astimezone(dt_timezone.utc)

            # 2. Filter & Annotate
            c = Community.objects.filter(id=community_id).annotate(
                daily_posts=Count('post', filter=Q(post__created_at__gte=current_start_utc), distinct=True),
                daily_likes=Count('post__likes', filter=Q(post__likes__created_at__gte=current_start_utc), distinct=True),
                daily_comments=Count('post__comments', filter=Q(post__comments__created_at__gte=current_start_utc), distinct=True),
                daily_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__gte=current_start_utc), distinct=True)
            ).first()

            if not c:
                return Response({"score": 0})

            score = (
                (c.daily_posts * 5) + 
                (c.daily_likes * 2) + 
                (c.daily_comments * 8) + 
                (c.daily_comment_likes * 1)
            )

            return Response({"score": score})
        except Exception as e:
            print(f"Score Calc Error: {e}")
            return Response({"score": 0})


class CommunityOnlineCountView(APIView):
    """
    Returns the number of users who have requested a feed in the last 60 seconds.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        # Redis pattern to find all active users in this specific community
        pattern = f"presence:{community_id}:*"
        
        # This returns a list of keys currently in Redis matching the pattern
        online_keys = redis_client.keys(pattern)
        
        return Response({
            "community_id": community_id,
            "online_count": len(online_keys)
        })