import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lecture_system.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model

User = get_user_model()

print('=== CURRENT TEACHER GROUP PERMISSIONS ===')
teacher_group = Group.objects.filter(name='Teacher').first()
if teacher_group:
    perms = list(teacher_group.permissions.values_list('codename', flat=True))
    print(f'Teacher group permissions: {perms}')
else:
    print('Teacher group not found!')

print('\n=== ADDING REQUIRED PERMISSIONS ===')
required_perms = [
    'add_generationrequest',
    'change_generationrequest',
    'view_generationrequest',
    'add_slidedraft',
    'change_slidedraft',
    'view_slidedraft',
]

if teacher_group:
    for perm_code in required_perms:
        perm = Permission.objects.filter(codename=perm_code, content_type__app_label='lectures').first()
        if perm:
            teacher_group.permissions.add(perm)
            print(f'  Added: {perm_code}')
        else:
            print(f'  NOT FOUND: {perm_code}')

print('\n=== MAKING ADMIN SUPERUSER ===')
admin_user = User.objects.filter(username='admin').first()
if admin_user:
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
    print(f'  admin is now superuser: {admin_user.is_superuser}')

print('\n=== UPDATED TEACHER GROUP PERMISSIONS ===')
if teacher_group:
    perms = list(teacher_group.permissions.values_list('codename', flat=True))
    print(f'Teacher group permissions: {perms}')

print('\nDone! Please restart the Django server and refresh the browser.')
