import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lecture_system.settings')
django.setup()

from django.contrib.auth import get_user_model
from lectures.models import Course, GenerationRequest, LectureDivision, ContentSource

User = get_user_model()
print('=== USERS ===')
for u in User.objects.all():
    groups = list(u.groups.values_list('name', flat=True))
    perms = list(u.user_permissions.values_list('codename', flat=True))
    print(f'  {u.username}: groups={groups}, perms={perms}, staff={u.is_staff}, superuser={u.is_superuser}')

print('\n=== COURSES ===')
for c in Course.objects.select_related('teacher').all():
    print(f'  {c.code}: {c.title} (teacher: {c.teacher.username if c.teacher else None})')

print('\n=== CONTENT SOURCES ===')
for s in ContentSource.objects.all():
    print(f'  ID={s.pk}: {s.title} - rights={s.rights_confirmed}, state={s.processing_state}')

print('\n=== LECTURE DIVISIONS ===')
for d in LectureDivision.objects.select_related('chapter__course').all():
    print(f'  {d.chapter.course.code} - Lec {d.number}: {d.title} (pages {d.page_start}-{d.page_end})')

print('\n=== GENERATION REQUESTS ===')
for g in GenerationRequest.objects.select_related('requested_by').all():
    print(f'  ID={g.pk}: by {g.requested_by.username}, status={g.status}, created={g.created_at}')
