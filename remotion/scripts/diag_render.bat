@echo off
rem Diagnostic: run the audited render.mjs adapter directly against the
rem existing render-v1 manifest to isolate the browser-connect timeout.
cd /d "E:\LMS Project\AI-Lecture-System-Agent-Workspace\remotion"
rem C: drive is full (839MB free) - chrome and render frames need temp space,
rem so run all temp writes on E: which has 74GB free.
set DIAG_TMP=E:\LMS Project\AI-Lecture-System-Agent-Workspace\data\tmp
if not exist "%DIAG_TMP%" mkdir "%DIAG_TMP%"
set TEMP=%DIAG_TMP%
set TMP=%DIAG_TMP%
set DIAG_MANIFEST=..\data\lectures\t050-video\workflow-10\render-v1-70b8e5f807026eabdb9cb86883fccd42ed5a6fc1\manifest.json
set DIAG_OUT=..\data\lectures\t050-video\diag-render.mp4
if exist "%DIAG_OUT%" del "%DIAG_OUT%"
if exist "%DIAG_OUT%.part.mp4" del "%DIAG_OUT%.part.mp4"
echo [%date% %time%] start render
node scripts\render.mjs "%DIAG_MANIFEST%" "%DIAG_OUT%"
echo [%date% %time%] render exit code %ERRORLEVEL%
