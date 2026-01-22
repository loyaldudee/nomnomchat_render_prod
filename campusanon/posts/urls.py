from django.urls import path
from .views import (
    CreatePostView,
    CommunityFeedView,
    DeletePostView,
    CreateCommentView,
    GetPostView,
    PostCommentsView,
    ToggleLikeView,
    ReportPostView,
    ReportCommentView,
    AdminBanUserView,
    AdminUnbanUserView,
    AdminUnhidePostView,
    AdminUnhideCommentView,
    AdminAuditLogView,
    SearchPostsView,
    LeaderboardView,
    CommunityScoreView
)

urlpatterns = [
    # Posts
    path("create/", CreatePostView.as_view(), name="create-post"),
    path("feed/<uuid:community_id>/", CommunityFeedView.as_view(), name="community-feed"),
    path("delete/<uuid:post_id>/", DeletePostView.as_view(), name="delete-post"),
    path("get/<uuid:post_id>/", GetPostView.as_view(), name="get-single-post"),

    # Comments
    path("comment/<uuid:post_id>/", CreateCommentView.as_view(), name="create-comment"),
    path("comment/<uuid:post_id>/list/", PostCommentsView.as_view(), name="list-comments"),

    path("like/<uuid:post_id>/", ToggleLikeView.as_view()),

    path("report/<uuid:post_id>/", ReportPostView.as_view(), name="report-post"),

    path("comment/report/<uuid:comment_id>/", ReportCommentView.as_view(), name="report-comment"),

     # Admin moderation
    path("admin/user/ban/<uuid:user_id>/", AdminBanUserView.as_view(), name="admin-ban-user"),
    path("admin/user/unban/<uuid:user_id>/", AdminUnbanUserView.as_view(), name="admin-unban-user"),

    path("admin/post/unhide/<uuid:post_id>/", AdminUnhidePostView.as_view(), name="admin-unhide-post"),
    path("admin/comment/unhide/<uuid:comment_id>/", AdminUnhideCommentView.as_view(), name="admin-unhide-comment"),
    path("admin/audit-logs/", AdminAuditLogView.as_view(), name="admin-audit-logs"),

    # Search
    path("search/", SearchPostsView.as_view(), name="search-posts"),

    path('leaderboard/', LeaderboardView.as_view()),
    path('<uuid:community_id>/score/', CommunityScoreView.as_view()),
]
