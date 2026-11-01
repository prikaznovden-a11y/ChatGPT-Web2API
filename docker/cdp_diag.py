#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Диагностика страницы ChatGPT внутри контейнера chatgpt-proxy.

Делает: Runtime.evaluate (текст body), список вкладок, Page.captureScreenshot.
Запуск:  docker cp cdp_diag.py chatgpt-proxy:/tmp/ && docker exec chatgpt-proxy python3 /tmp/cdp_diag.py
"""
import asyncio
import base64
import json
import urllib.request

import websockets

CDP = "http://127.0.0.1:9222"


def tabs():
    with urllib.request.urlopen(CDP + "/json/list", timeout=10) as r:
        return json.loads(r.read().decode())


async def evaluate(ws, expr, mid):
    await ws.send(json.dumps({
        "id": mid, "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
    }))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if msg.get("id") == mid:
            r = msg.get("result", {}).get("result", {})
            return r.get("value")


async def main():
    t = tabs()
    print("=== ВКЛАДКИ ===")
    for x in t:
        print("  ", x.get("type"), "|", (x.get("title") or "")[:50], "|", (x.get("url") or "")[:90])

    page = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
    if not page:
        print("вкладки chatgpt нет")
        return

    ws_url = page["webSocketDebuggerUrl"]
    async with websockets.connect(ws_url, max_size=80 * 1024 * 1024) as ws:
        info = await evaluate(ws, "JSON.stringify({url:location.href,title:document.title,ready:document.readyState})", 1)
        print("\n=== СТРАНИЦА ===\n ", info)

        body = await evaluate(ws, "document.body ? document.body.innerText.slice(0,3000) : 'NO BODY'", 2)
        print("\n=== ТЕКСТ СТРАНИЦЫ (первые 3000) ===\n", body)

        cnt = await evaluate(ws, """JSON.stringify({
            prose: document.querySelectorAll('[data-message-author-role="assistant"]').length,
            user: document.querySelectorAll('[data-message-author-role="user"]').length,
            composer: document.querySelectorAll('#prompt-textarea, textarea[data-virtualkeyboard="true"]').length,
            stop: document.querySelectorAll('button[aria-label*="Stop"], button[data-testid="stop-button"]').length
        })""", 3)
        print("\n=== СЧЁТЧИКИ DOM ===\n ", cnt)

        await ws.send(json.dumps({"id": 4, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if msg.get("id") == 4:
                data = msg.get("result", {}).get("data")
                if data:
                    with open("/tmp/chatgpt_page.png", "wb") as f:
                        f.write(base64.b64decode(data))
                    print("\nскриншот: /tmp/chatgpt_page.png")
                break


asyncio.run(main())
