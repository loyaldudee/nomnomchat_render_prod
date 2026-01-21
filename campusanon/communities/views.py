from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.core.cache import cache
from .models import Community, CommunityMembership

class MyCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. GENERATE A UNIQUE CACHE KEY
        # We need different keys for Admin vs Normal users
        is_admin = user.is_staff or user.is_superuser
        cache_key = f"communities_admin" if is_admin else f"communities_user_{user.id}"
        
        # 2. CHECK REDIS FIRST
        cached_data = cache.get(cache_key)
        if cached_data:
            print("⚡ Serving from Cache (Fast!)") 
            return Response(cached_data)

        # ---------------------------------------------------------
        # 👑 GOD MODE CHECK (Staff/Superuser)
        # ---------------------------------------------------------
        # If you are Staff or Superuser, you bypass all filters and see EVERYTHING.
        # This matches the logic we set up in CreatePostView.
        if user.is_staff or user.is_superuser:
            print(f"👑 ADMIN DETECTED ({user.username}): Showing ALL communities")
            all_communities = Community.objects.all()
        else:
            # -----------------------------------------------------
            # NORMAL STUDENT LOGIC
            # -----------------------------------------------------
            
            # 1. AUTOMATIC: Get communities matching User's Branch, Year, or Global
            # Logic: (Global) OR (Matches Branch) OR (Matches Year)
            auto_communities = Community.objects.filter(
                Q(is_global=True) |
                (
                    (Q(branch=user.branch) | Q(branch__isnull=True) | Q(branch='')) &
                    (Q(year=user.year) | Q(year__isnull=True))
                )
            ).exclude(
                # Filter out "ghost" communities that have no settings
                is_global=False, branch__isnull=True, year__isnull=True
            )

            # 2. MANUAL: Get communities the user specifically joined (e.g. Clubs)
            joined_ids = CommunityMembership.objects.filter(
                user=user
            ).values_list('community_id', flat=True)
            
            manual_communities = Community.objects.filter(id__in=joined_ids)

            # 3. COMBINE: Merge both lists and remove duplicates
            all_communities = (auto_communities | manual_communities).distinct()

        # 4. Serialize
        data = []
        for c in all_communities:
            data.append({
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "is_global": c.is_global,
                "branch": c.branch, # Helpful for frontend to show subtitles
                "year": c.year
            })

        # 5. SAVE TO REDIS (for 15 minutes)
        # 900 seconds = 15 minutes
        cache.set(cache_key, data, timeout=900)

        return Response(data)

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