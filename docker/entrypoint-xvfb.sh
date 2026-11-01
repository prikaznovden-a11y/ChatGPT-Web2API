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

# ── Чистка X-сервера ────────────────────────────────────────────────────
# При рестарте контейнера (docker restart) старый Xvfb может ещё ЖИТЬ (он
# осиротел после exec, и Docker не всегда успевает его убить), а новый
# Xvfb на том же :99 падает с "Server is already active for display 99"
# из-за оставшегося /tmp/.X99-lock. Через пару секунд старый Xvfb умирает -
# и Chrome остаётся без дисплея ("Missing X server or $DISPLAY").
#
# Поэтому: убиваем ЛЮБОЙ Xvfb, снимаем lock и socket, и только потом
# поднимаем новый. Проверка готовности - не только xdpyinfo (он соединится
# и со СТАРЫМ сервером), но и то, что наш процесс Xvfb жив.
pkill -f "Xvfb" 2>/dev/null || true
sleep 1
rm -f "/tmp/.X${DISPLAY#:}-lock" "/tmp/.X11-unix/X${DISPLAY#:}" 2>/dev/null || true

Xvfb "$DISPLAY" -screen 0 1920x1080x24 -nolisten tcp -ac >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!

# Ждём, пока наш Xvfb реально поднимется и начнёт отвечать.
XVFB_OK=0
for i in $(seq 1 60); do
    if ! kill -0 "$XVFB_PID" 2>/dev/null; then
        echo "Xvfb НЕ ПОДНЯЛСЯ (pid $XVFB_PID умер):" >&2
        tail -5 /tmp/xvfb.log >&2 2>/dev/null || true
        break
    fi
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        XVFB_OK=1
        echo "Xvfb готов на $DISPLAY (pid $XVFB_PID)"
        break
    fi
    sleep 0.5
done

if [ "$XVFB_OK" != "1" ]; then
    echo "ОШИБКА: нет рабочего X-сервера на $DISPLAY - Chrome не запустится" >&2
    exit 1
fi
# Профиль Chrome переживает рестарт контейнера (/data/chrome-profile - том).
# Если контейнер был убит нештатно, в профиле остаются файлы
# SingletonLock/SingletonCookie/SingletonSocket от мёртвого процесса.
# Chrome видит такой lock, считает что "браузер уже запущен", печатает
# "Opening in existing browser session." и НЕ поднимает CDP-порт - шлюз
# падает с "Chrome CDP did not respond within 30s".
# Перед стартом Chrome удаляем эти lock-файлы: в контейнере других процессов
# Chrome нет, ломать нечего.
rm -f /data/chrome-profile/SingletonLock \
      /data/chrome-profile/SingletonCookie \
      /data/chrome-profile/SingletonSocket 2>/dev/null || true
echo "Устаревшие блокировки профиля Chrome очищены"

# ── Прогрев Chrome до запуска приложения ────────────────────────────────
# Приложение само запускает Chrome и ждёт CDP 30 c, потом убивает его и
# падает с "Chrome CDP did not respond within 30s". С тёплым профилем
# (сотни МБ, восстановление сессии) Chrome открывает debug-порт дольше - особенно
# сразу после рестарта контейнера, когда page cache холодный. Наблюдалось:
# recreate - ок, restart - падение.
#
# Поэтому запускаем Chrome ЗДЕСЬ и ждём CDP с большим запасом. Приложение
# потом подключится к уже работающему Chrome ("Found existing Chrome on CDP
# port 9222") и не будет запускать свой.
CHROME_BIN="${W2A_CHROME_PATH:-/usr/local/bin/chrome-wrapper}"
CDP_PORT="${W2A_CDP_PORT:-9222}"
PROFILE_DIR="${W2A_USER_DATA_DIR:-/data/chrome-profile}"

echo "Прогрев Chrome (CDP $CDP_PORT, профиль $PROFILE_DIR)..."
setsid "$CHROME_BIN" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-background-networking \
    --disable-default-apps \
    --disable-hang-monitor \
    --disable-popup-blocking \
    --disable-prompt-on-repost \
    --disable-sync \
    --metrics-recording-only \
    --safebrowsing-disable-auto-update \
    https://chatgpt.com >/tmp/chrome-warmup.log 2>&1 &

CDP_READY=0
# curl --max-time 1: иначе итерация занимает 1 c (curl) + 1 c (sleep) = 2 c,
# и весь лимит в 180 c растягивается вдвое.
for i in $(seq 1 180); do
    if curl -s --max-time 1 "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
        echo "Chrome CDP готов (${i} c)"
        CDP_READY=1
        break
    fi
    sleep 1
done

if [ "$CDP_READY" != "1" ]; then
    echo "ВНИМАНИЕ: Chrome CDP не поднялся за 180 c - передаю управление приложению (оно попробует само)" >&2
    tail -20 /tmp/chrome-warmup.log >&2 2>/dev/null || true
fi

cleanup() {
    kill "$XVFB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /docker-entrypoint.sh "$@"
