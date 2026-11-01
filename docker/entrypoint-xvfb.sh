#!/bin/bash
# Entrypoint с виртуальным дисплеем (Xvfb) для ChatGPT-Web2API.
#
# Порядок:
#   1) Поднимаем Xvfb на :99 (виртуальный дисплей для headed Chrome).
#   2) Ждём готовности дисплея.
#   3) Передаём управление штатному entrypoint оригинала
#      (/docker-entrypoint.sh): он сам поднимает proxy, дожидается Chrome CDP
#      и инжектит cookies из /data/cookies/cookies.json.
set -e

export DISPLAY=:99

if ! command -v Xvfb >/dev/null 2>&1; then
    echo "Xvfb не найден в образе - запускаю штатный entrypoint без дисплея"
    exec /docker-entrypoint.sh "$@"
fi

# Убираем возможный старый Xvfb на том же дисплее.
pkill -f "Xvfb $DISPLAY" 2>/dev/null || true

Xvfb "$DISPLAY" -screen 0 1920x1080x24 -nolisten tcp -ac >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!

# Ждём, пока дисплей поднимется (обычно 1-3 c).
for i in $(seq 1 30); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        echo "Xvfb готов на $DISPLAY (pid $XVFB_PID)"
        break
    fi
    sleep 0.5
done

cleanup() {
    kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /docker-entrypoint.sh "$@"
