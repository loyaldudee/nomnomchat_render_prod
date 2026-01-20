from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Community, CommunityMembership

class MyCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # ✅ HARDCODED: If it is YOU, return ALL communities
        email_hash = getattr(request.user, 'email_hash', '')
        user_email_raw = request.user.email or email_hash or ""
        user_email = str(user_email_raw).lower().strip()
        target_email = "rishimayur_22539@aitpune.edu.in"

        if user_email == target_email:
            # Admin sees EVERYTHING
            all_communities = Community.objects.all()
        else:
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