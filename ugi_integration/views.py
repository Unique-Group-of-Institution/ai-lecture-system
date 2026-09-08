from django.shortcuts import redirect
from django.contrib.auth import login
from django.http import JsonResponse
from django.conf import settings
from .token import verify_launch_token
from .models import ExternalIdentityLink
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

def launch(request):
    token = request.GET.get('token') or request.POST.get('token')
    if not token:
        return JsonResponse({'error': 'Missing token'}, status=400)
    
    claims = verify_launch_token(token)
    if not claims:
        return JsonResponse({'error': 'Invalid or expired token'}, status=401)
    
    ext_user_id = claims.get('sub')
    email = claims.get('email')
    if not ext_user_id or not email:
        return JsonResponse({'error': 'Missing identity'}, status=400)
    
    # Get or create local user
    try:
        link = ExternalIdentityLink.objects.select_related('local_user').get(
            provider='ugi_crm', external_user_id=ext_user_id, status='active'
        )
        user = link.local_user
    except ExternalIdentityLink.DoesNotExist:
        # Create local user if not exists
        user, created = User.objects.get_or_create(
            username=email,
            defaults={'email': email, 'is_active': True}
        )
        if created:
            user.set_unusable_password()
            user.save()
        link = ExternalIdentityLink.objects.create(
            provider='ugi_crm',
            external_user_id=ext_user_id,
            local_user=user,
            email_snapshot=email,
        )
    
    if not user.is_active:
        return JsonResponse({'error': 'User inactive'}, status=403)
    
    # For now, allow all active users. Later we can check LMS roles.
    # Create Django session
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Redirect to dashboard or next param
    next_url = request.GET.get('next', '/')
    # Safe redirect: only local paths
    if next_url.startswith('/'):
        return redirect(next_url)
    else:
        return redirect('/')