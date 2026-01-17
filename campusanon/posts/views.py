from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from communities.models import Community
from accounts.models import User
from .models import (
    Post,
    Comment,
    PostLike,
    PostReport,
    CommentReport,
)
from .utils import generate_alias, is_rate_limited
from .permissions import IsAdminUser

REPORT_THRESHOLD = 3
COMMENT_REPORT_THRESHOLD = 3
PAGE_SIZE = 20
COMMENT_PAGE_SIZE = 20  # Added for comment pagination


# -------------------------------
# CREATE POST
# -------------------------------
class CreatePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Security check for banned users
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Rate Limiting (3 posts per 5 minutes)
        if is_rate_limited(
            request.user,
            action="create_post",
            limit=3,
            window_seconds=300
        ):
            return Response(
                {"error": "Too many posts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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

        cursor = request.query_params.get("cursor")

        posts = Post.objects.filter(
            community_id=community_id,
            is_hidden=False
        )

        if cursor:
            cursor_dt = parse_datetime(cursor)
            if cursor_dt:
                posts = posts.filter(created_at__lt=cursor_dt)

        # ✅ FIX: Convert to list to support negative indexing
        posts = list(
            posts.order_by("-created_at")[:PAGE_SIZE]
        )

        data = [
            {
                "id": str(p.id),
                "alias": p.alias,
                "content": p.content,
                "created_at": p.created_at,
                "likes_count": p.likes.count(),
            }
            for p in posts
        ]

        next_cursor = None
        if posts:
            next_cursor = posts[-1].created_at.isoformat()

        return Response({
            "results": data,
            "next_cursor": next_cursor
        })


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
        # 1. Security check for banned users
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Rate Limiting (10 comments per 5 minutes)
        if is_rate_limited(
            request.user,
            action="create_comment",
            limit=10,
            window_seconds=300
        ):
            return Response(
                {"error": "Too many comments. Slow down."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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

        cursor = request.query_params.get("cursor")

        # Filter out hidden comments
        comments = post.comments.filter(is_hidden=False)

        # Cursor pagination logic for comments (ascending order)
        if cursor:
            cursor_dt = parse_datetime(cursor)
            if cursor_dt:
                comments = comments.filter(created_at__gt=cursor_dt)

        # ✅ FIX: Convert to list for safe indexing
        comments = list(
            comments.order_by("created_at")[:COMMENT_PAGE_SIZE]
        )

        data = [
            {
                "id": str(c.id),
                "alias": c.alias,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in comments
        ]

        next_cursor = None
        if comments:
            next_cursor = comments[-1].created_at.isoformat()

        return Response({
            "results": data,
            "next_cursor": next_cursor
        })


class ToggleLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        # 1. Security check for banned users
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Rate Limiting (30 likes per minute)
        if is_rate_limited(
            request.user,
            action="like",
            limit=30,
            window_seconds=60
        ):
            return Response(
                {"error": "Too many actions. Slow down."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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
        # 1. Security check for banned users
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Rate Limiting (5 reports per 10 minutes)
        if is_rate_limited(
            request.user,
            action="report",
            limit=5,
            window_seconds=600
        ):
            return Response(
                {"error": "Too many reports. Try later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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
        # 1. Security check for banned users
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. Rate Limiting (5 reports per 10 minutes)
        if is_rate_limited(
            request.user,
            action="report",
            limit=5,
            window_seconds=600
        ):
            return Response(
                {"error": "Too many reports. Try later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

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


class AdminUnhidePostView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, post_id):
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        post.is_hidden = False
        post.save()

        return Response({"message": "Post unhidden"})


class AdminUnhideCommentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, comment_id):
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        comment.is_hidden = False
        comment.save()

        return Response({"message": "Comment unhidden"})


class AdminBanUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_banned = True
        user.save()

        return Response({"message": "User banned"})


class AdminUnbanUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_banned = False
        user.save()

        return Response({"message": "User unbanned"})