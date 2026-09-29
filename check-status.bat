@echo off
cd /d "E:\LMS Project\AI-Lecture-System-Agent-Workspace"

set AI_LECTURE_SECRET_KEY=dev-secret-key-change-in-production-12345
set AI_LECTURE_DEBUG=true
set AI_LECTURE_ALLOWED_HOSTS=localhost,127.0.0.1
set AI_LECTURE_CSRF_TRUSTED_ORIGINS=http://localhost:8000
set DATABASE_URL=sqlite:///data/ai_lecture_system.sqlite3
set AI_LECTURE_DATA_ROOT=data
set MEDIA_ROOT=data
set YOUTUBE_WATCH_FOLDER=data/exports/youtube-watch
set AI_LECTURE_CONTENT_MAX_BYTES=104857600
set LOG_LEVEL=INFO
set UGI_CRM_SSO_SIGNING_SECRET=dev-crm-secret-change-in-production-67890
set AI_LECTURE_DEPLOYMENT_MODE=disabled
set AI_LECTURE_LOCAL_EXECUTION_HOST=localhost
set AI_LECTURE_VIDEO_RENDER_ADAPTER=0
set AI_LECTURE_REMOTION_EVALUATION_ACK=

python manage.py shell -c "
from django.contrib.auth import get_user_model
from lectures.models import Course, GenerationRequest, LectureDivision, ContentSource
from django.contrib.auth.models import Group, Permission

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
"
pause
