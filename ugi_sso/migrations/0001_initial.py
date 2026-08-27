# Generated for UGI shared-login integration.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ExternalIdentityLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="ugi-crm", max_length=32)),
                ("subject", models.CharField(max_length=128)),
                ("email_at_link", models.EmailField(blank=True, max_length=254)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="external_identity_links", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["provider", "subject", "active"], name="ext_identity_lookup_idx")],
                "constraints": [models.UniqueConstraint(fields=("provider", "subject"), name="unique_external_identity_subject")],
            },
        ),
        migrations.CreateModel(
            name="ConsumedLaunchToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="ugi-crm", max_length=32)),
                ("jti", models.CharField(max_length=128, unique=True)),
                ("subject", models.CharField(max_length=128)),
                ("consumed_at", models.DateTimeField(auto_now_add=True)),
                ("consumed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consumed_launch_tokens", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-consumed_at", "pk")},
        ),
    ]
