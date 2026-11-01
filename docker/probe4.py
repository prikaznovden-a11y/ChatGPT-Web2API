import asyncio, json, urllib.request, websockets
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
            return "JS ERROR: " + str(r.get("description"))[:300] if r.get("subtype") == "error" else r.get("value")


# Селекторы ровно как в PR #55 + наш markdown-text-style
PROBE = r"""
(()=>{const o={};const q=s=>Array.from(document.querySelectorAll(s));
const PR55='[data-message-author-role="assistant"], [data-content-search-unit-key$=":assistant"], [data-chatgpt-search-unit-key$=":assistant"]';
o.pr55Count=q(PR55).length;
o.pr55Nodes=q(PR55).map(e=>({tag:e.tagName.toLowerCase(),
  contentSearchKey:e.getAttribute('data-content-search-unit-key'),
  chatgptSearchKey:e.getAttribute('data-chatgpt-search-unit-key'),
  convRole:e.getAttribute('data-conversation-role'),
  mdStyle:e.getAttribute('data-markdown-text-style'),
  innerText:(e.innerText||'').slice(0,150),
  hasMarkdownChild:!!e.querySelector('.markdown'),
  mdChildText:e.querySelector('.markdown')?(e.querySelector('.markdown').textContent||'').slice(0,100):null,
  htmlLen:e.innerHTML.length, children:e.children.length}));
const PR55U='[data-message-author-role="user"], [data-content-search-unit-key$=":user"], [data-chatgpt-search-unit-key$=":user"]';
o.pr55UserCount=q(PR55U).length;
o.pr55UserNodes=q(PR55U).map(e=>({tag:e.tagName.toLowerCase(),innerText:(e.innerText||'').slice(0,100)}));
// наш дополнительный: markdown-text-style
const MD='[data-markdown-text-style="assistant-message"]';
o.mdCount=q(MD).length;
o.mdNodes=q(MD).map(e=>({innerText:(e.innerText||'').slice(0,150),htmlLen:e.innerHTML.length}));
// кнопки действий: чем они размечены сейчас
o.buttons=q('button').filter(b=>b.offsetWidth||b.offsetHeight).map(b=>({al:b.getAttribute('aria-label'),tid:b.getAttribute('data-testid'),cls:(typeof b.className==='string'?b.className:'').slice(0,50)})).slice(0,25);
// stop-кнопка
o.stopBtn=q('button[aria-label*="Stop" i]').length;
o.stopTestid=q('[data-testid*="stop" i]').length;
return JSON.stringify(o,null,1)})()
"""


async def main():
    t = tabs()
    p = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
    if not p:
        print("нет вкладки")
        return
    async with websockets.connect(p["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
        print(await ev(ws, PROBE, 1))


asyncio.run(main())
