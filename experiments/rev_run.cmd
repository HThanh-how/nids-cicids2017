@echo off
cd /d "%~dp0"
set REV_STAGES=R1,R2,R3,R4
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
echo START %DATE% %TIME% > rev_run.log
python run_revision.py >> rev_run.log 2>&1
echo EXIT %ERRORLEVEL% %DATE% %TIME% >> rev_run.log
