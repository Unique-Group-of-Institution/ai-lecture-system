from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ExternalIdentityLink(models.Model):
    provider = models.CharField(max_length=50, default='ugi_crm')
    external_user_id = models.CharField(max_length=255, unique=True)
    local_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='external_links')
    email_snapshot = models.EmailField()
    linked_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, default='active')  # active, inactive, blocked
    metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = [('provider', 'external_user_id')]