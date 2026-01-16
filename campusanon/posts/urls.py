from django.urls import path
from .views import CreatePostView, CommunityFeedView

urlpatterns = [
    path("create/", CreatePostView.as_view()),
    path("feed/<uuid:community_id>/", CommunityFeedView.as_view()),
    
]
