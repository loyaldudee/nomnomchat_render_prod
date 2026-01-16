from django.urls import path
from .views import (
    CreatePostView,
    CommunityFeedView,
    DeletePostView,
    CreateCommentView,
    PostCommentsView,
    ToggleLikeView
)

urlpatterns = [
    # Posts
    path("create/", CreatePostView.as_view(), name="create-post"),
    path("feed/<uuid:community_id>/", CommunityFeedView.as_view(), name="community-feed"),
    path("delete/<uuid:post_id>/", DeletePostView.as_view(), name="delete-post"),

    # Comments
    path("comment/<uuid:post_id>/", CreateCommentView.as_view(), name="create-comment"),
    path("comment/<uuid:post_id>/list/", PostCommentsView.as_view(), name="list-comments"),

    path("like/<uuid:post_id>/", ToggleLikeView.as_view()),
]
