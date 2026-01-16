import uuid
from django.db import models
from accounts.models import User
from communities.models import Community


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)

    # 🔒 Anonymous identity (changes per post)
    alias = models.CharField(max_length=50)

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alias} in {self.community.name}"
