@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe wsgi.py
) else (
  python wsgi.py
)
