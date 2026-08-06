from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate, dispatch_uid="lectures.ensure_phase_one_roles")
def create_phase_one_roles(sender, **kwargs) -> None:
    if sender.label == "lectures":
        from .roles import ensure_roles

        ensure_roles()
