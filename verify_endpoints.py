import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lecture_system.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ["testserver"]

User = get_user_model()

CHECKS = [
    ('GET', '/'),
    ('GET', '/studio/'),
    ('GET', '/api/generations/10/'),
    ('GET', '/api/workflows/'),
    ('GET', '/studio/lecture/10/'),
    ('GET', '/teacher/recordings/'),
    ('GET', '/admin/video-assembly/'),
]

for username in ('bilal.ali', 'admin'):
    user = User.objects.get(username=username)
    client = Client()
    client.force_login(user)
    print(f'=== {username} ===')
    for method, url in CHECKS:
        response = client.get(url)
        flag = 'OK ' if response.status_code in (200, 302) else 'BAD'
        print(f'  {flag} {response.status_code} {url}')
    pptx = client.get('/api/generations/10/export-pptx/')
    print(f'  {"OK " if pptx.status_code == 200 else "BAD"} {pptx.status_code} /api/generations/10/export-pptx/ ({"bytes" if pptx.status_code == 200 else pptx.content[:60]})')
