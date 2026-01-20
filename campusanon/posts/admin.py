from django.contrib import admin
from django.db.models import Count
from .models import Post, Comment, PostReport, CommentReport, AdminAuditLog, PostLike

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    # ✅ Added 'reports_count' to list_display
    list_display = ('alias', 'community', 'is_hidden', 'created_at', 'short_content', 'likes_count', 'reports_count')
    list_filter = ('is_hidden', 'community')
    search_fields = ('content', 'alias')
    
    def short_content(self, obj):
        return obj.content[:50]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # ✅ Annotate BOTH likes and reports for sorting
        return queryset.annotate(
            total_likes=Count('likes'),
            total_reports=Count('reports')
        )

    @admin.display(description='Likes', ordering='total_likes')
    def likes_count(self, obj):
        return obj.total_likes

    # ✅ NEW: Column for Reports
    @admin.display(description='Reports', ordering='total_reports')
    def reports_count(self, obj):
        return obj.total_reports

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('alias', 'post', 'is_hidden', 'created_at')
    list_filter = ('is_hidden',)

@admin.register(PostReport)
class PostReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'post', 'reason', 'created_at')

# ✅ NEW: Register CommentReport so you can see it in Admin
@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'comment', 'reason', 'created_at')

@admin.register(AdminAuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('admin', 'action', 'target_type', 'reason', 'created_at')
    list_filter = ('action', 'target_type')

@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at',)