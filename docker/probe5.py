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
            return "ERR:" + str(r.get("description"))[:200] if r.get("subtype") == "error" else r.get("value")


PROBE = r"""
(()=>{const o={};const q=s=>Array.from(document.querySelectorAll(s));
const desc=e=>({tag:e.tagName.toLowerCase(),
  turnKey:e.getAttribute('data-turn-key'), turnState:e.getAttribute('data-talvt-turn-state'),
  csk:e.getAttribute('data-chatgpt-search-unit-key'), csk2:e.getAttribute('data-content-search-unit-key'),
  convRole:e.getAttribute('data-conversation-role'), mdStyle:e.getAttribute('data-markdown-text-style'),
  txt:(e.innerText||'').slice(0,40), depth:(()=>{let d=0,p=e;while(p&&p!==document.body){d++;p=p.parentElement}return d})()});
// элементы с turn-state
o.turnStateEls=q('[data-talvt-turn-state]').map(desc);
o.turnKeyEls=q('[data-turn-key]').map(desc);
// элементы с chatgpt-search-unit-key
o.searchKeyEls=q('[data-chatgpt-search-unit-key]').map(desc);
// markdown-style
o.mdStyleEls=q('[data-markdown-text-style]').map(desc);
// отношение: является ли turn-state элемент предком search-key элемента?
const asst=q('[data-chatgpt-search-unit-key$=":assistant"]');
const last=asst.length?asst[asst.length-1]:null;
if(last){
  let p=last,chain=[];
  for(let i=0;i<10&&p;i++){chain.push(p.tagName.toLowerCase()+'['+(p.getAttribute('data-talvt-turn-state')||p.getAttribute('data-turn-key')||p.getAttribute('data-chatgpt-search-unit-key')||'')+']');p=p.parentElement;}
  o.ancestorChain=chain;
  // ищем turn-state среди предков
  o.ancestorTurnState=(()=>{let p=last;while(p){const v=p.getAttribute&&p.getAttribute('data-talvt-turn-state');if(v)return v;p=p.parentElement}return null})();
  // turn-key среди предков
  o.ancestorTurnKey=(()=>{let p=last;while(p){const v=p.getAttribute&&p.getAttribute('data-turn-key');if(v)return v;p=p.parentElement}return null})();
  // clean text контейнер внутри last
  const mdEl=last.querySelector('[data-markdown-text-style="assistant-message"], .markdown');
  o.cleanEl=mdEl?desc(mdEl):null;
  o.cleanText=mdEl?(mdEl.innerText||'').slice(0,120):null;
  o.cleanTextContent=mdEl?(mdEl.textContent||'').slice(0,120):null;
  // copy-кнопки внутри last и рядом
  const cp=q('button[aria-label*="Copy" i]').filter(b=>b.offsetWidth||b.getClientRects().length);
  o.copyBtns=cp.map(b=>{const r=b.getBoundingClientRect();return {al:b.getAttribute('aria-label'),top:Math.round(r.top),inLast:!!b.closest('[data-chatgpt-search-unit-key$=":assistant"]')}});
  o.lastRect=(()=>{const r=last.getBoundingClientRect();return {top:Math.round(r.top),bottom:Math.round(r.bottom)}})();
}
o.url=location.href;
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
