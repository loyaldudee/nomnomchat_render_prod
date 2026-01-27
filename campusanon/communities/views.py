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
from datetime import timedelta

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
        # 1. DEFINE TIME WINDOWS (The 6 AM Rule)
        # ---------------------------------------------------------
        now = timezone.now()
        
        # Define "Today 6 AM"
        today_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
        
        # If it's currently 4 AM, the "competition day" actually started yesterday at 6 AM.
        if now < today_6am:
            current_start = today_6am - timedelta(days=1)
        else:
            current_start = today_6am

        # Previous day (for finding yesterday's winner)
        prev_start = current_start - timedelta(days=1)
        prev_end = current_start

        # ---------------------------------------------------------
        # 2. CACHE CHECK
        # ---------------------------------------------------------
        # We cache this for 5 minutes so we don't hammer the DB
        cache_key = f"leaderboard_daily_v1_{current_start.strftime('%Y%m%d')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        response_data = {}

        # ---------------------------------------------------------
        # 3. GENERATE LEADERBOARD PER YEAR
        # ---------------------------------------------------------
        # We loop through years 1 to 4
        for year in [1, 2, 3, 4]:
            
            # A. GET LIVE STANDINGS (Since 6 AM)
            # We filter actions that happened >= current_start
            live_communities = Community.objects.filter(year=year, is_global=False).annotate(
                # Count actions within the time window
                daily_posts=Count('post', filter=Q(post__created_at__gte=current_start), distinct=True),
                daily_likes=Count('post__likes', filter=Q(post__likes__created_at__gte=current_start), distinct=True),
                daily_comments=Count('post__comments', filter=Q(post__comments__created_at__gte=current_start), distinct=True),
                daily_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__gte=current_start), distinct=True)
            )

            leaderboard_list = []
            for c in live_communities:
                # 🧮 DAILY SCORE FORMULA
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

            # Sort by Score (Highest First)
            leaderboard_list.sort(key=lambda x: x['score'], reverse=True)
            
            # Add Rank
            for idx, item in enumerate(leaderboard_list):
                item['rank'] = idx + 1


            # B. GET YESTERDAY'S WINNER
            # We filter actions in the range [prev_start, prev_end]
            past_communities = Community.objects.filter(year=year, is_global=False).annotate(
                past_posts=Count('post', filter=Q(post__created_at__range=(prev_start, prev_end)), distinct=True),
                past_likes=Count('post__likes', filter=Q(post__likes__created_at__range=(prev_start, prev_end)), distinct=True),
                past_comments=Count('post__comments', filter=Q(post__comments__created_at__range=(prev_start, prev_end)), distinct=True),
                past_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__range=(prev_start, prev_end)), distinct=True)
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

            # C. ASSEMBLE YEAR DATA
            response_data[year] = {
                "live_leaderboard": leaderboard_list,
                "yesterday_winner": winner_data  # Can be null if no activity yesterday
            }

        # ---------------------------------------------------------
        # 4. SAVE TO CACHE
        # ---------------------------------------------------------
        cache.set(cache_key, response_data, timeout=300)

        return Response(response_data)


class CommunityScoreView(APIView):
    """ Get the DAILY score for just ONE community (using the 6 AM rule) """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        try:
            # 1. Calculate Time Window
            now = timezone.now()
            today_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now < today_6am:
                current_start = today_6am - timedelta(days=1)
            else:
                current_start = today_6am

            # 2. Filter & Annotate (Same as Leaderboard)
            c = Community.objects.filter(id=community_id).annotate(
                daily_posts=Count('post', filter=Q(post__created_at__gte=current_start), distinct=True),
                daily_likes=Count('post__likes', filter=Q(post__likes__created_at__gte=current_start), distinct=True),
                daily_comments=Count('post__comments', filter=Q(post__comments__created_at__gte=current_start), distinct=True),
                daily_comment_likes=Count('post__comments__likes', filter=Q(post__comments__likes__created_at__gte=current_start), distinct=True)
            ).first()

            if not c:
                return Response({"score": 0})

            # 🧮 SAME FORMULA
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