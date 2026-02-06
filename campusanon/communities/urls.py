from django.urls import path
from .views import (
    MyCommunitiesView, 
    SearchCommunitiesView, 
    LeaderboardView,     
    CommunityScoreView,
    CommunityOnlineCountView,
)

urlpatterns = [
    # 1. Main Dashboard List (matches /communities/)
    path("", MyCommunitiesView.as_view(), name="my-communities"),
    
    # 2. Search
    path("search/", SearchCommunitiesView.as_view(), name="search-communities"),

    # ✅ 3. ADD THIS: Leaderboard (matches /communities/leaderboard/)
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),

    # ✅ 4. ADD THIS: Score (matches /communities/<id>/score/)
    path("<uuid:community_id>/score/", CommunityScoreView.as_view(), name="community-score"),

    path("<uuid:community_id>/online/", CommunityOnlineCountView.as_view(), name="community-online-count"),
]