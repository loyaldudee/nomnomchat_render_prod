from django.contrib import admin
from django.db.models import Count
from .models import Post, Comment, PostReport, CommentReport, AdminAuditLog, PostLike

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('alias', 'community', 'is_hidden', 'created_at', 'short_content', 'likes_count', 'reports_count')
    list_filter = ('is_hidden', 'community')
    search_fields = ('content', 'alias')
    
    # ✅ 1. ALLOW MANUAL EDITING
    # This adds a toggle switch directly in the list view
    list_editable = ('is_hidden',) 
    
    def short_content(self, obj):
        return obj.content[:50]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # ✅ 2. FIX DOUBLE COUNTING
        # distinct=True prevents the "multiplication" of rows
        return queryset.annotate(
            total_likes=Count('likes', distinct=True),
            total_reports=Count('reports', distinct=True)
        )

    @admin.display(description='Likes', ordering='total_likes')
    def likes_count(self, obj):
        return obj.total_likes

    @admin.display(description='Reports', ordering='total_reports')
    def reports_count(self, obj):
        return obj.total_reports
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    # ✅ Added 'reports_count'
    list_display = ('alias', 'post', 'is_hidden', 'created_at', 'reports_count')
    list_filter = ('is_hidden',)
    
    # ✅ Optimize query to count reports
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(total_reports=Count('reports'))

    # ✅ Define the column
    @admin.display(description='Reports', ordering='total_reports')
    def reports_count(self, obj):
        return obj.total_reports

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