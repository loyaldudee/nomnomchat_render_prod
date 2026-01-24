import uuid
from django.db import models
from accounts.models import User

class Community(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    year = models.IntegerField(null=True, blank=True)  # 1, 2, 3, 4
    branch = models.CharField(max_length=50, null=True, blank=True) # COMP, IT, etc.
    division = models.CharField(max_length=10, null=True, blank=True) # A, B, or None
    
    is_global = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures we don't accidentally create duplicate "1st Year COMP A" entries
        unique_together = ('year', 'branch', 'division')

    def __str__(self):
        div_str = f" {self.division}" if self.division else ""
        return f"{self.year} {self.branch}{div_str}"

class CommunityMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community")

    def __str__(self):
        return f"{self.user_id} -> {self.community.name}"