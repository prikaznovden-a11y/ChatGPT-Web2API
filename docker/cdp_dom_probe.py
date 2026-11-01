#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор реальной структуры DOM ответа ChatGPT (новый UI).

Ищем, чем сейчас размечен блок ассистента, вместо устаревшего
[data-message-author-role="assistant"].
"""
import asyncio
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
            if r.get("subtype") == "error":
                return "JS ERROR: " + str(r.get("description"))[:300]
            return r.get("value")


PROBE = r"""
(() => {
  const out = {};
  // 1) Ищем узел, где текст "ChatGPT said" или сам ответ
  const all = Array.from(document.querySelectorAll('article, [data-message-id], [data-testid], div'));
  // Ищем узлы, у которых в data-* есть что-то про автора/роль
  const attrs = {};
  document.querySelectorAll('*').forEach(el => {
    for (const a of el.attributes) {
      if (a.name.startsWith('data-') && /role|author|msg|message|turn/i.test(a.name + ' ' + a.value)) {
        attrs[a.name] = a.value.slice(0, 40);
      }
    }
  });
  out.dataAttrs = attrs;

  // 2) Все article с текстом
  out.articles = Array.from(document.querySelectorAll('article')).map(a => ({
    cls: a.className.slice(0, 80),
    text: a.innerText.slice(0, 120)
  }));

  // 3) Кандидаты: узлы с текстом "Работает"
  out.hasAnswerText = document.body.innerText.includes('Работает');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let cand = [];
  let n;
  while ((n = walker.nextNode()) && cand.length < 12) {
    if (n.children.length === 0 && /Работает/.test(n.textContent || '')) {
      let p = n, chain = [];
      for (let i = 0; i < 5 && p; i++) {
        chain.push(p.tagName.toLowerCase() + (p.className && typeof p.className === 'string' ? '.' + p.className.split(' ').slice(0,3).join('.') : '') + (p.getAttribute('data-testid') ? '[' + p.getAttribute('data-testid') + ']' : ''));
        p = p.parentElement;
      }
      cand.push(chain.join(' < '));
    }
  }
  out.answerChains = cand;

  // 4) textarea/composer
  out.textareas = Array.from(document.querySelectorAll('textarea')).map(t => ({
    id: t.id, ph: t.placeholder, vis: !!(t.offsetWidth || t.offsetHeight), cls: t.className.slice(0,60)
  }));
  out.contenteditables = Array.from(document.querySelectorAll('[contenteditable="true"]')).map(t => ({
    id: t.id, testid: t.getAttribute('data-testid'), vis: !!(t.offsetWidth || t.offsetHeight)
  }));
  return JSON.stringify(out, null, 1);
})()
"""


async def main():
    t = tabs()
    page = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
    if not page:
        print("вкладки chatgpt нет")
        return
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
        res = await evaluate(ws, PROBE, 1)
        print(res)


asyncio.run(main())
