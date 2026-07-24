#!/bin/sh
set -eu

backend_pid=""
nginx_pid=""

terminate() {
    if [ -n "$backend_pid" ]; then
        kill -TERM "$backend_pid" 2>/dev/null || true
    fi
    if [ -n "$nginx_pid" ]; then
        kill -TERM "$nginx_pid" 2>/dev/null || true
    fi
}

trap terminate INT TERM

gunicorn --workers 1 --no-control-socket --bind 127.0.0.1:8081 main:app &
backend_pid=$!

attempt=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/ping', timeout=1)" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if ! kill -0 "$backend_pid" 2>/dev/null || [ "$attempt" -ge 30 ]; then
        echo "Backend failed to become ready" >&2
        terminate
        wait "$backend_pid" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

nginx -g "daemon off;" &
nginx_pid=$!

while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

status=0
if ! kill -0 "$backend_pid" 2>/dev/null; then
    wait "$backend_pid" || status=$?
fi
if ! kill -0 "$nginx_pid" 2>/dev/null; then
    wait "$nginx_pid" || status=$?
fi

terminate
wait "$backend_pid" 2>/dev/null || true
wait "$nginx_pid" 2>/dev/null || true
exit "$status"
