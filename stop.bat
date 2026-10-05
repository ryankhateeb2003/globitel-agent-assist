@echo off
REM Stops all project containers (the API stops with the app container).
cd /d "%~dp0"
docker compose stop
