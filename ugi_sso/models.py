from django.conf import settings
from django.db import models


class ExternalIdentityLink(models.Model):
    provider = models.CharField(max_length=32, default="ugi-crm")
    subject = models.CharField(max_length=128)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="external_identity_links",
    )
    email_at_link = models.EmailField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "subject"),
                name="unique_external_identity_subject",
            )
        ]
        indexes = [models.Index(fields=("provider", "subject", "active"), name="ext_identity_lookup_idx")]

    def __str__(self) -> str:
        return f"{self.provider}:{self.subject} -> {self.user_id}"


class ConsumedLaunchToken(models.Model):
    provider = models.CharField(max_length=32, default="ugi-crm")
    jti = models.CharField(max_length=128, unique=True)
    subject = models.CharField(max_length=128)
    consumed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="consumed_launch_tokens",
    )
    consumed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-consumed_at", "pk")

    def __str__(self) -> str:
        return f"{self.provider}:{self.jti}"
