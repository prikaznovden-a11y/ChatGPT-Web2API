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


PROBE = r"""
(()=>{const o={};const q=s=>Array.from(document.querySelectorAll(s));
const md=q('[data-markdown-text-style="assistant-message"]');
o.mdCount=md.length;
o.mdInfo=md.map(e=>({tag:e.tagName.toLowerCase(),
 cls:(typeof e.className==='string'?e.className:'').slice(0,90),
 innerText:(e.innerText||'').slice(0,120), textContent:(e.textContent||'').slice(0,120),
 htmlLen:e.innerHTML.length, children:e.children.length,
 parentChain:(()=>{let c=[],p=e;for(let i=0;i<7&&p;i++){c.push(p.tagName.toLowerCase()+'['+(p.getAttribute('data-testid')||p.getAttribute('data-talvt-turn-state')||p.getAttribute('data-conversation-role')||'')+']'+(typeof p.className==='string'?'.'+p.className.split(' ').slice(0,2).join('.'):''));p=p.parentElement;}return c;})()}));
o.turnState=q('[data-talvt-turn-state]').map(e=>({v:e.getAttribute('data-talvt-turn-state'),txt:(e.innerText||'').slice(0,60)}));
o.userBubble=q('[data-user-message-bubble]').map(e=>({tag:e.tagName.toLowerCase(),txt:(e.innerText||'').slice(0,80)}));
o.turnKey=q('[data-turn-key]').map(e=>({tag:e.tagName.toLowerCase(),txt:(e.innerText||'').slice(0,80)}));
o.actionBtns=q('button').filter(b=>b.offsetWidth||b.offsetHeight).map(b=>({al:b.getAttribute('aria-label'),tid:b.getAttribute('data-testid')})).filter(x=>(x.tid&&/copy|like|dislike|thumb|reader|more/i.test(x.tid))||(x.al&&/copy|like|dislike/i.test(x.al))).slice(0,12);
o.allTestids=[...new Set(q('[data-testid]').map(e=>e.getAttribute('data-testid')))].slice(0,50);
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
