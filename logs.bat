@echo off
REM Short command to watch the server's live logs from a SECOND terminal,
REM while start.bat keeps running the server in the first one.
REM Shows the last 50 lines, then keeps following new ones -- Ctrl+C to stop
REM watching (does NOT stop the server itself).
docker exec globitel-app tail -n 50 -f /tmp/uvicorn_globitel.log
