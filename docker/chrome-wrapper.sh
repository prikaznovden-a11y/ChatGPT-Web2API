#!/bin/bash
# Обёртка Chrome для запуска от root в контейнере.
#
# Зачем: Chrome под root падает с
#   "Running as root without --no-sandbox is not supported"
# (zygote_host_impl_linux.cc). Проект chatgpt-web2api не имеет env/CLI-опции
# для доп. аргументов Chrome (ChromeConfig.extra_args нигде не заполняется),
# поэтому добавляем флаги здесь и указываем путь через W2A_CHROME_PATH.
#
# --disable-dev-shm-usage: /dev/shm в Docker по умолчанию 64 МБ, Chrome
# на нём падает (render process crashed). shm_size в compose это тоже лечит.
set -e
exec /usr/bin/google-chrome \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    "$@"
