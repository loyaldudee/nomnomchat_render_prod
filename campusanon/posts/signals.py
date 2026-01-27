from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import PostReport, CommentReport, PostLike, Comment, Notification # ✅ Import Notification
from django.core.cache import cache
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



@receiver(post_save, sender=PostLike)
def notify_on_like(sender, instance, created, **kwargs):
    if created:
        post = instance.post
        # Don't notify if I like my own post
        if instance.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                actor=instance.user,
                verb='like',
                post=post
            )
            cache.set(f"has_notif_{post.user.id}", True, timeout=86400)

@receiver(post_save, sender=Comment)
def notify_on_comment(sender, instance, created, **kwargs):
    if created:
        post = instance.post
        # Don't notify if I comment on my own post
        if instance.user != post.user:
             Notification.objects.create(
                recipient=post.user,
                actor=instance.user,
                verb='comment',
                post=post
            )
             ache.set(f"has_notif_{post.user.id}", True, timeout=86400)