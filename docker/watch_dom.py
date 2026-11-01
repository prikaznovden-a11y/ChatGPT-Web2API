import asyncio, json, time, urllib.request, websockets
CDP = "http://127.0.0.1:9222"


def tabs():
    return json.loads(urllib.request.urlopen(CDP + "/json/list", timeout=10).read().decode())


async def ev(ws, expr, mid):
    await ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                               "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if m.get("id") == mid:
            r = m.get("result", {}).get("result", {})
            return {} if r.get("subtype") == "error" else (r.get("value") or {})


# Ровно тот же JS, что использует детектор (PR55-селекторы), плюс новые признаки.
JS = r"""
(()=>{
 const q=s=>Array.from(document.querySelectorAll(s));
 const SEL='[data-message-author-role="assistant"], [data-content-search-unit-key$=":assistant"], [data-chatgpt-search-unit-key$=":assistant"]';
 const msgs=q(SEL);
 const last=msgs[msgs.length-1];
 const md=last?last.querySelector('.markdown'):null;
 const mdText=md?(md.textContent||''):'';
 const rawText=last?(last.innerText||'').trim():'';
 // новая разметка
 const mdStyle=q('[data-markdown-text-style="assistant-message"]');
 const mdStyleLast=mdStyle.length?mdStyle[mdStyle.length-1]:null;
 const turnState=q('[data-talvt-turn-state]').map(e=>e.getAttribute('data-talvt-turn-state'));
 // кнопка копирования: по aria-label
 const copyBtns=q('button[aria-label*="Copy" i]').filter(b=>b.offsetWidth||b.getClientRects().length);
 // testid-кнопки (как ищет детектор)
 const ACT='[data-testid="copy-turn-action-button"],[data-testid="good-response-turn-action-button"],[data-testid="bad-response-turn-action-button"],[data-testid*="turn-action-button"],[data-testid*="copy"],[data-testid*="response-turn"]';
 const actBtns=q(ACT);
 const stop=q('button[aria-label*="Stop" i]').length;
 return {
  msgCount: msgs.length,
  htmlLen: last?last.innerHTML.length:0,
  childCount: last?last.children.length:0,
  mdText: mdText.slice(0,120),
  rawText: rawText.slice(0,120),
  mdStyleCount: mdStyle.length,
  mdStyleText: mdStyleLast?(mdStyleLast.innerText||'').slice(0,120):null,
  turnState: turnState,
  copyAriaCount: copyBtns.length,
  actTestidCount: actBtns.length,
  stopBtn: stop,
  url: location.href.slice(0,90)
 };
})()
"""


async def main():
    dur = int(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 120
    t0 = time.time()
    seen = set()
    while time.time() - t0 < dur:
        try:
            t = tabs()
            p = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
            if not p:
                await asyncio.sleep(2); continue
            async with websockets.connect(p["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
                d = await ev(ws, JS, 1)
            key = json.dumps({k: d.get(k) for k in ("msgCount", "htmlLen", "mdStyleCount", "turnState", "copyAriaCount", "actTestidCount", "stopBtn")}, sort_keys=True)
            if key not in seen:
                seen.add(key)
                print("[%5.1fs] %s" % (time.time() - t0, json.dumps(d, ensure_ascii=False)[:420]))
                sys.stdout.flush()
        except Exception as e:
            print("ERR", e)
        await asyncio.sleep(1.5)


import sys
asyncio.run(main())
