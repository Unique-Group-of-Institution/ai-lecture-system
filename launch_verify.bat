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
set AI_LECTURE_DEPLOYMENT_MODE=local-evaluation
set AI_LECTURE_LOCAL_EXECUTION_HOST=127.0.0.1
set AI_LECTURE_VIDEO_RENDER_ADAPTER=1
set AI_LECTURE_REMOTION_EVALUATION_ACK=evaluation-only-2026-08-20
python .codex\scratch\verify_ui.py
