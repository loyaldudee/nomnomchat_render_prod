from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from communities.models import Community
from .models import Post, Comment, PostLike, PostReport
from .utils import generate_alias
from .models import CommentReport


REPORT_THRESHOLD = 3
COMMENT_REPORT_THRESHOLD = 3


# -------------------------------
# CREATE POST
# -------------------------------
class CreatePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        community_id = request.data.get("community_id")
        content = request.data.get("content")

        if not community_id or not content:
            return Response(
                {"error": "community_id and content required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {"error": "Community not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        post = Post.objects.create(
            user=request.user,
            community=community,
            content=content,
            alias=generate_alias(),
        )

        return Response(
            {
                "id": str(post.id),
                "alias": post.alias,
                "content": post.content,
                "created_at": post.created_at,
            },
            status=status.HTTP_201_CREATED
        )


# -------------------------------
# COMMUNITY FEED
# -------------------------------
class CommunityFeedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        try:
            Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {"error": "Community not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        posts = (
        Post.objects
        .filter(community_id=community_id, is_hidden=False)
        .order_by("-created_at")[:50]
        )


        return Response([
        {
            "id": str(p.id),
            "alias": p.alias,
            "content": p.content,
            "created_at": p.created_at,
            "likes_count": p.likes.count(),
        }
        for p in posts
    ])



# -------------------------------
# DELETE OWN POST
# -------------------------------
class DeletePostView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if post.user != request.user:
            return Response(
                {"error": "Not allowed to delete this post"},
                status=status.HTTP_403_FORBIDDEN
            )

        post.delete()

        return Response(
            {"message": "Post deleted successfully"},
            status=status.HTTP_200_OK
        )


# -------------------------------
# CREATE COMMENT
# -------------------------------
class CreateCommentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        content = request.data.get("content")

        if not content:
            return Response(
                {"error": "content required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        comment = Comment.objects.create(
            post=post,
            user=request.user,
            content=content,
            alias=generate_alias(),
        )

        return Response(
            {
                "id": str(comment.id),
                "alias": comment.alias,
                "content": comment.content,
                "created_at": comment.created_at,
            },
            status=status.HTTP_201_CREATED
        )


# -------------------------------
# LIST COMMENTS FOR A POST
# -------------------------------
class PostCommentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        comments = post.comments.filter(is_hidden=False)


        return Response([
            {
                "id": str(c.id),
                "alias": c.alias,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in comments
        ])


class ToggleLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        like, created = PostLike.objects.get_or_create(
            user=request.user,
            post=post
        )

        if not created:
            # already liked → unlike
            like.delete()
            return Response({
                "liked": False,
                "likes_count": post.likes.count()
            })

        return Response({
            "liked": True,
            "likes_count": post.likes.count()
        })



class ReportPostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        reason = request.data.get("reason", "unspecified")

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if post.is_hidden:
            return Response(
                {"message": "Post already hidden"},
                status=status.HTTP_200_OK
            )

        report, created = PostReport.objects.get_or_create(
            post=post,
            reporter=request.user,
            defaults={"reason": reason}
        )

        if not created:
            return Response(
                {"message": "Already reported"},
                status=status.HTTP_200_OK
            )

        # 🔒 Auto-hide logic
        if post.reports.count() >= REPORT_THRESHOLD:
            post.is_hidden = True
            post.save()

        return Response({
            "message": "Reported successfully",
            "reports_count": post.reports.count(),
            "hidden": post.is_hidden
        })



class ReportCommentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id):
        reason = request.data.get("reason", "unspecified")

        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if comment.is_hidden:
            return Response(
                {"message": "Comment already hidden"},
                status=status.HTTP_200_OK
            )

        report, created = CommentReport.objects.get_or_create(
            comment=comment,
            reporter=request.user,
            defaults={"reason": reason}
        )

        if not created:
            return Response(
                {"message": "Already reported"},
                status=status.HTTP_200_OK
            )

        # 🔒 Auto-hide after threshold
        if comment.reports.count() >= COMMENT_REPORT_THRESHOLD:
            comment.is_hidden = True
            comment.save()

        return Response({
            "message": "Reported successfully",
            "reports_count": comment.reports.count(),
            "hidden": comment.is_hidden
        })