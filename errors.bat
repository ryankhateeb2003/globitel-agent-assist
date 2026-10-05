@echo off
REM Short command to see ONLY the errors from the server's log -- scans
REM the last 500 lines for "ERROR"/"Traceback"/"Exception" and shows them
REM with a few lines of context around each, instead of the full log.
docker exec globitel-app sh -c "tail -n 500 /tmp/uvicorn_globitel.log | grep -i -B2 -A15 'error\|traceback\|exception'"
