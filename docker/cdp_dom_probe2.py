#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Глубокий зондж DOM нового UI ChatGPT - готовим патч селекторов."""
import asyncio
import json
import urllib.request

import websockets

CDP = "http://127.0.0.1:9222"


def tabs():
    with urllib.request.urlopen(CDP + "/json/list", timeout=10) as r:
        return json.loads(r.read().decode())


async def ev(ws, expr, mid):
    await ws.send(json.dumps({
        "id": mid, "method": "Runtime.evaluate",
        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
    }))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if msg.get("id") == mid:
            r = msg.get("result", {}).get("result", {})
            if r.get("subtype") == "error":
                return "JS ERROR: " + str(r.get("description"))[:400]
            return r.get("value")


PROBE = r"""
(() => {
  const o = {};
  const q = s => Array.from(document.querySelectorAll(s));

  // A) Какие значения бывают у data-conversation-role
  o.convRoles = {};
  q('[data-conversation-role]').forEach(e => {
    const v = e.getAttribute('data-conversation-role');
    o.convRoles[v] = (o.convRoles[v] || 0) + 1;
  });

  // B) Узлы ассистента по новому селектору
  const as = q('[data-conversation-role="assistant"]');
  o.assistantCount = as.length;
  o.assistantInfo = as.map(a => ({
    tag: a.tagName.toLowerCase(),
    cls: (typeof a.className === 'string' ? a.className : '').slice(0, 70),
    testid: a.getAttribute('data-testid'),
    mdStyle: a.getAttribute('data-markdown-text-style'),
    innerText: (a.innerText || '').slice(0, 100),
    hasMarkdownCls: !!a.querySelector('.markdown'),
    mdText: a.querySelector('.markdown') ? a.querySelector('.markdown').textContent.slice(0, 80) : null,
    htmlLen: a.innerHTML.length,
    children: a.children.length,
    turnState: a.getAttribute('data-talvt-turn-state')
  }));

  // C) Узлы пользователя
  const us = q('[data-conversation-role="user"]');
  o.userCount = us.length;
  o.userInfo = us.map(a => ({
    tag: a.tagName.toLowerCase(),
    cls: (typeof a.className === 'string' ? a.className : '').slice(0, 70),
    innerText: (a.innerText || '').slice(0, 80),
    bubble: a.getAttribute('data-user-message-bubble')
  }));

  // D) Старые селекторы для сравнения
  o.oldAssistant = q('[data-message-author-role="assistant"]').length;
  o.oldUser = q('[data-message-author-role="user"]').length;

  // E) .markdown в принципе есть на странице?
  o.markdownClassTotal = q('.markdown').length;
  o.markdownSample = q('.markdown').map(m => (m.textContent || '').slice(0, 60)).slice(0, 5);

  // F) data-markdown-text-style
  o.mdStyles = {};
  q('[data-markdown-text-style]').forEach(e => {
    const v = e.getAttribute('data-markdown-text-style');
    o.mdStyles[v] = (o.mdStyles[v] || 0) + 1;
  });

  // G) Composer
  o.composerProseMirror = q('div[role="textbox"].ProseMirror').length;
  o.composerAny = q('[role="textbox"]').length;

  // H) Кнопка стоп (индикатор генерации)
  o.stopBtn = q('button[aria-label*="Stop" i]').length;

  // I) Контейнер с data-turn-key (это у юзера)
  o.turnKeys = q('[data-turn-key]').length;

  return JSON.stringify(o, null, 1);
})()
"""


async def main():
    t = tabs()
    page = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
    if not page:
        print("вкладки chatgpt нет")
        return
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
        print(await ev(ws, PROBE, 1))


asyncio.run(main())
