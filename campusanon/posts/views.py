from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Post
from .utils import generate_alias
from communities.models import Community


class CreatePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        community_id = request.data.get("community_id")
        content = request.data.get("content")

        if not community_id or not content:
            return Response(
                {"error": "community_id and content required"},
                status=400
            )

        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response({"error": "Community not found"}, status=404)

        post = Post.objects.create(
            user=request.user,
            community=community,
            content=content,
            alias=generate_alias(),
        )

        return Response({
            "id": str(post.id),
            "alias": post.alias,
            "content": post.content,
            "created_at": post.created_at,
        }, status=201)



class CommunityFeedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        try:
            Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {"error": "Community not found"},
                status=404
            )

        posts = (
            Post.objects
            .filter(community_id=community_id)
            .order_by("-created_at")[:50]
        )

        return Response([
            {
                "id": str(p.id),
                "alias": p.alias,
                "content": p.content,
                "created_at": p.created_at,
            }
            for p in posts
        ])
