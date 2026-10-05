@echo off
REM Starts the containers (qdrant, ollama, app) and runs the API in the foreground,
REM so its logs show in this terminal. Press Ctrl+C to stop the server.
cd /d "%~dp0"
docker compose up -d
REM Restart the app container so no older background server is still holding port 8000.
docker compose restart app
echo.
echo Server starting at http://localhost:8000  -- wait for "Application startup complete"
echo Press Ctrl+C to stop.
echo.
REM tee also writes every log line to /tmp/uvicorn_globitel.log inside the
REM container, so a second terminal can run logs.bat to watch the same
REM output without taking over this one.
docker exec -it globitel-app sh -c "uvicorn app.api.main:app --host 0.0.0.0 --port 8000 2>&1 | tee /tmp/uvicorn_globitel.log"
