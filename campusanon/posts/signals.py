from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import PostReport, CommentReport

# We match the thresholds from your views.py
REPORT_THRESHOLD = 3
COMMENT_REPORT_THRESHOLD = 3

@receiver(post_delete, sender=PostReport)
def check_post_reports_on_delete(sender, instance, **kwargs):
    post = instance.post
    # Count remaining reports
    count = post.reports.count()
    
    # If it was hidden but now has fewer reports than threshold, unhide it
    if post.is_hidden and count < REPORT_THRESHOLD:
        post.is_hidden = False
        post.save()
        print(f"✅ Auto-unhidden Post {post.alias} (Reports dropped to {count})")

@receiver(post_delete, sender=CommentReport)
def check_comment_reports_on_delete(sender, instance, **kwargs):
    comment = instance.comment
    count = comment.reports.count()
    
    if comment.is_hidden and count < COMMENT_REPORT_THRESHOLD:
        comment.is_hidden = False
        comment.save()
        print(f"✅ Auto-unhidden Comment {comment.alias} (Reports dropped to {count})")