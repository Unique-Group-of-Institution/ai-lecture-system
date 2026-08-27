from django.contrib import admin

from .models import ConsumedLaunchToken, ExternalIdentityLink


@admin.register(ExternalIdentityLink)
class ExternalIdentityLinkAdmin(admin.ModelAdmin):
    list_display = ("provider", "subject", "user", "email_at_link", "active", "updated_at")
    list_filter = ("provider", "active")
    search_fields = ("subject", "email_at_link", "user__username", "user__email")
    autocomplete_fields = ("user",)


@admin.register(ConsumedLaunchToken)
class ConsumedLaunchTokenAdmin(admin.ModelAdmin):
    list_display = ("provider", "jti", "subject", "consumed_by", "consumed_at")
    list_filter = ("provider",)
    search_fields = ("jti", "subject", "consumed_by__username", "consumed_by__email")
    readonly_fields = ("provider", "jti", "subject", "consumed_by", "consumed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
