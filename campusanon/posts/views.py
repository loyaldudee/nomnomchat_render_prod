from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.db.models import Count, Exists, OuterRef
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from communities.models import Community, CommunityMembership # Check your paths
from django.db.models import Q

from communities.models import Community
from accounts.models import User
from .models import (
    Post,
    Comment,
    PostLike,
    PostReport,
    CommentReport,
    AdminAuditLog,  # ✅ Imported Model
)
from .utils import (
    generate_alias, 
    is_rate_limited_redis, 
    log_admin_action  # ✅ Imported Helper
)
from .permissions import IsAdminUser

REPORT_THRESHOLD = 3
COMMENT_REPORT_THRESHOLD = 3
PAGE_SIZE = 20
COMMENT_PAGE_SIZE = 20


# -------------------------------
# CREATE POST
# -------------------------------
class CreatePostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.is_banned:
            return Response({"error": "User is banned"}, status=status.HTTP_403_FORBIDDEN)

        # ---------------------------------------------------------
        # 👑 THE "GOD MODE" CHECK
        # ---------------------------------------------------------
        # We check your specific ID from the admin panel + superuser status
        MY_ADMIN_ID = "c021ac82-dba5-4205-92ff-aff96859b4de"
        
        is_god_mode = (
            request.user.is_superuser or 
            request.user.is_staff or 
            str(request.user.id) == MY_ADMIN_ID
        )

        # 🔍 DEBUG: Prove it works in the terminal
        print(f"\n---- ADMIN CHECK ----")
        print(f"User ID:    {request.user.id}")
        print(f"Is Super?   {request.user.is_superuser}")
        print(f"Is Staff?   {request.user.is_staff}")
        print(f"GOD MODE:   {is_god_mode}")
        print(f"---------------------\n")

        # 1. RATE LIMIT (Bypass for God Mode)
        if not is_god_mode:
            if is_rate_limited_redis(request.user.id, action="create_post", limit=3, window_seconds=300):
                return Response({"error": "Too many posts."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        community_id = request.data.get("community_id")
        content = request.data.get("content")

        if not community_id or not content:
            return Response({"error": "Data required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response({"error": "Community not found"}, status=status.HTTP_404_NOT_FOUND)

        # 2. ALIAS (loyaldude for God Mode)
        if is_god_mode:
            post_alias = "loyaldude"
            print("✅ Assigning loyaldude (Admin Bypass)")
        else:
            post_alias = generate_alias()

        post = Post.objects.create(
            user=request.user,
            community=community,
            content=content,
            alias=post_alias, 
        )

        return Response({
            "id": str(post.id),
            "alias": post.alias,
            "content": post.content,
            "created_at": post.created_at,
            "is_mine": True,            # 👈 ADD THIS LINE
            "is_liked": False,          # 👈 Good to have default
            "likes_count": 0,           # 👈 Good to have default
            "is_reported": False        # 👈 Good to have default
        }, status=status.HTTP_201_CREATED)


# -------------------------------
# COMMUNITY FEED
# -------------------------------
class CommunityFeedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        user = request.user

        # 1. Get Community (or 404)
        community = get_object_or_404(Community, id=community_id)

        # ---------------------------------------------------------
        # 🔒 SECURITY CHECK (The "Bouncer")
        # ---------------------------------------------------------
        # We must verify if the user is actually allowed to see this feed.
        
        has_access = False

        # Rule 1: Allow if Community is Global (All)
        if community.is_global:
            has_access = True
            
        # Rule 2: Allow if User is Admin/Staff (God Mode)
        elif user.is_staff or user.is_superuser:
            has_access = True

        # Rule 3: Allow if User matches Year AND Branch
        # (e.g. If community is "3 IT", user must be Year 3 and Branch IT)
        # Note: If community.year is None, it ignores year (e.g. "All IT Students")
        elif (
            (community.year is None or community.year == user.year) and 
            (community.branch is None or community.branch == user.branch)
        ):
            has_access = True
            
        # Rule 4: Allow if User is explicitly a member (e.g. joined a club manually)
        elif CommunityMembership.objects.filter(user=user, community=community).exists():
            has_access = True

        # 🚨 FINAL VERDICT
        if not has_access:
            return Response(
                {"error": "🚫 Access Denied: You do not belong to this community."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ---------------------------------------------------------
        # 🚀 OPTIMIZED QUERY (Your original logic)
        # ---------------------------------------------------------
        
        cursor = request.query_params.get("cursor")

        # Subquery: Did THIS user like the post?
        is_liked_by_user = PostLike.objects.filter(
            post=OuterRef('pk'),
            user=user
        )

        # Subquery: Did THIS user report the post?
        is_reported_by_user = PostReport.objects.filter(
            post=OuterRef('pk'),
            reporter=user
        )

        # Main Query with Annotation
        posts = Post.objects.filter(
            community=community,  # Filter by the secure community object
            is_hidden=False
        ).annotate(
            # Count likes directly in DB
            total_likes=Count('likes'),
            # Boolean checks
            is_liked=Exists(is_liked_by_user),
            is_reported=Exists(is_reported_by_user)
        )

        # Cursor Pagination Logic
        if cursor:
            cursor_dt = parse_datetime(cursor)
            if cursor_dt:
                posts = posts.filter(created_at__lt=cursor_dt)

        # Order & Slice
        posts = list(
            posts.order_by("-created_at")[:PAGE_SIZE]
        )

        # Serialize Data
        data = [
            {
                "id": str(p.id),
                "alias": p.alias,
                "content": p.content,
                "created_at": p.created_at,
                "likes_count": p.total_likes,
                "is_liked": p.is_liked,
                "is_mine": p.user_id == user.id,
                "is_reported": p.is_reported
            }
            for p in posts
        ]

        # Calculate Next Cursor
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
        if request.user.is_banned:
            return Response({"error": "User is banned"}, status=status.HTTP_403_FORBIDDEN)

        # ---------------------------------------------------------
        # 👑 THE "GOD MODE" CHECK
        # ---------------------------------------------------------
        # We check your specific ID from the admin panel + superuser status
        MY_ADMIN_ID = "c021ac82-dba5-4205-92ff-aff96859b4de"
        
        is_god_mode = (
            request.user.is_superuser or 
            request.user.is_staff or 
            str(request.user.id) == MY_ADMIN_ID
        )

        # 🔍 DEBUG: Prove it works in the terminal
        print(f"\n---- ADMIN CHECK (Comment) ----")
        print(f"User ID:    {request.user.id}")
        print(f"Is Super?   {request.user.is_superuser}")
        print(f"Is Staff?   {request.user.is_staff}")
        print(f"GOD MODE:   {is_god_mode}")
        print(f"--------------------------------\n")

        # 1. RATE LIMIT (Bypass for God Mode)
        if not is_god_mode:
            if is_rate_limited_redis(request.user.id, action="create_comment", limit=10, window_seconds=300):
                return Response({"error": "Too many comments."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        content = request.data.get("content")
        if not content:
            return Response({"error": "content required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        # 2. ALIAS (loyaldude for God Mode)
        if is_god_mode:
            comment_alias = "loyaldude"
            print("✅ Assigning loyaldude (Admin Bypass)")
        else:
            comment_alias = generate_alias()

        comment = Comment.objects.create(
            post=post,
            user=request.user,
            content=content,
            alias=comment_alias,
        )

        return Response({
            "id": str(comment.id),
            "alias": comment.alias,
            "content": comment.content,
            "created_at": comment.created_at,
            "is_mine": True,            # 👈 ADD THIS LINE
            "is_reported": False        # 👈 Good to have default
        }, status=status.HTTP_201_CREATED)


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

        # 👇 1. Define the Subquery (Did I report this?)
        is_reported_by_user = CommentReport.objects.filter(
            comment=OuterRef('pk'),
            reporter=request.user
        )

        # 👇 2. Filter & Annotate
        comments = post.comments.filter(is_hidden=False).annotate(
            is_reported=Exists(is_reported_by_user)
        )

        if cursor:
            cursor_dt = parse_datetime(cursor)
            if cursor_dt:
                comments = comments.filter(created_at__gt=cursor_dt)

        comments = list(
            comments.order_by("created_at")[:COMMENT_PAGE_SIZE]
        )

        # 👇 3. Send "is_reported" and "is_mine" to frontend
        data = [
            {
                "id": str(c.id),
                "alias": c.alias,
                "content": c.content,
                "created_at": c.created_at,
                "is_mine": c.user_id == request.user.id,
                "is_reported": c.is_reported  # ✅ Checks if user reported it
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
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Redis Rate Limiting
        if is_rate_limited_redis(
            request.user.id,
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
            like.delete()
            return Response({
                "liked": False,
                "likes_count": post.likes.count()
            })

        return Response({
            "liked": True,
            "likes_count": post.likes.count()
        })

class GetPostView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        # Subquery to check if user liked this specific post
        is_liked_by_user = PostLike.objects.filter(
            post=OuterRef('pk'),
            user=request.user
        )

        # Report subquery
        is_reported_by_user = PostReport.objects.filter(
            post=OuterRef('pk'),
            reporter=request.user
        )

        try:
            # We use filter() + first() instead of get() to allow annotation
            post = Post.objects.filter(id=post_id).annotate(
                total_likes=Count('likes'),
                is_liked=Exists(is_liked_by_user),
                is_reported=Exists(is_reported_by_user)
            ).first()
            
            if not post:
                return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

            return Response({
            "id": str(post.id),
            "alias": post.alias,
            "content": post.content,
            "created_at": post.created_at,
            "likes_count": post.total_likes,
            "is_liked": post.is_liked,
            "community_id": str(post.community.id),
            "community_name": post.community.name,
            "is_mine": post.user_id == request.user.id,
            "is_reported": post.is_reported
        })

        except Exception as e:
            print(e)
            return Response({"error": "Error fetching post"}, status=500)


class ReportPostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Redis Rate Limiting
        if is_rate_limited_redis(
            request.user.id,
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
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. Redis Rate Limiting
        if is_rate_limited_redis(
            request.user.id,
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

        # ✅ LOGGING
        log_admin_action(
            admin=request.user,
            action="UNHIDE_POST",
            target_id=post.id,
            target_type="Post"
        )

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

        # ✅ LOGGING
        log_admin_action(
            admin=request.user,
            action="UNHIDE_COMMENT",
            target_id=comment.id,
            target_type="Comment"
        )

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

        # ✅ LOGGING
        log_admin_action(
            admin=request.user,
            action="BAN_USER",
            target_id=user.id,
            target_type="User",
            reason=request.data.get("reason", "")
        )

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

        # ✅ LOGGING
        log_admin_action(
            admin=request.user,
            action="UNBAN_USER",
            target_id=user.id,
            target_type="User"
        )

        return Response({"message": "User unbanned"})


# ✅ NEW: Read-only Audit Log API
class AdminAuditLogView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        logs = AdminAuditLog.objects.all()[:100]

        return Response([
            {
                "admin_id": str(log.admin_id),
                "action": log.action,
                "target_type": log.target_type,
                "target_id": str(log.target_id),
                "reason": log.reason,
                "created_at": log.created_at,
            }
            for log in logs
        ])
    

class SearchPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 🛡️ Ban Safety Check
        if request.user.is_banned:
            return Response(
                {"error": "User is banned"},
                status=status.HTTP_403_FORBIDDEN
            )

        query = request.query_params.get("q", "").strip()
        community_id = request.query_params.get("community_id")

        if not query:
            return Response([], status=status.HTTP_200_OK)

        # 👇 1. Define the "Is Liked?" Subquery
        is_liked_by_user = PostLike.objects.filter(
            post=OuterRef('pk'),
            user=request.user
        )

        # 👇 1b. Define the "Is Reported?" Subquery
        is_reported_by_user = PostReport.objects.filter(
            post=OuterRef('pk'),
            reporter=request.user
        )

        # 👇 2. Filter & Annotate
        posts = Post.objects.filter(
            content__icontains=query,
            is_hidden=False
        )

        if community_id:
            posts = posts.filter(community_id=community_id)

        # Add the "intelligence" (Counts + Flags)
        posts = posts.annotate(
            total_likes=Count('likes'),
            is_liked=Exists(is_liked_by_user),
            is_reported=Exists(is_reported_by_user)
        ).order_by("-created_at")[:50]  # Limit to 50 results

        # 👇 3. Return rich data
        return Response([
            {
                "id": str(p.id),
                "alias": p.alias,
                "content": p.content,
                "created_at": p.created_at,
                "likes_count": p.total_likes,
                "is_liked": p.is_liked,       # ✅ Interactive Heart
                "is_mine": p.user_id == request.user.id, # ✅ Interactive Delete
                "is_reported": p.is_reported,
                "community_id": str(p.community_id),
            }
            for p in posts
        ])