import asyncio, json, sys, time, urllib.request, websockets
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


JS = r"""
(()=>{
 const q=s=>Array.from(document.querySelectorAll(s));
 const SEL='[data-message-author-role="assistant"], [data-content-search-unit-key$=":assistant"], [data-chatgpt-search-unit-key$=":assistant"]';
 const msgs=q(SEL);
 const last=msgs.length?msgs[msgs.length-1]:null;
 const mdStyle=q('[data-markdown-text-style="assistant-message"]');
 const mdLast=mdStyle.length?mdStyle[mdStyle.length-1]:null;
 const mdLegacy=last?last.querySelector('.markdown'):null;
 // turn-state предок ПОСЛЕДНЕГО ассистент-узла
 let turnState=null,p=last;
 while(p){const v=p.getAttribute&&p.getAttribute('data-talvt-turn-state');if(v){turnState=v;break;}p=p.parentElement;}
 // все turn-state на странице
 const allTurnStates=q('[data-talvt-turn-state]').map(e=>e.getAttribute('data-talvt-turn-state'));
 // copy-кнопки
 const cp=q('button[aria-label*="Copy" i]').filter(b=>b.offsetWidth||b.getClientRects().length);
 const cpLast=last?last.getBoundingClientRect():null;
 let copyNear=false;
 cp.forEach(b=>{const r=b.getBoundingClientRect();
   if(cpLast && r.top>=cpLast.top-180 && r.top<=cpLast.bottom+240) copyNear=true;});
 return {
  n: msgs.length,
  htmlLen: last?last.innerHTML.length:0,
  mdStyleCount: mdStyle.length,
  mdStyleLen: mdLast?(mdLast.innerText||'').length:0,
  mdStyleTxt: mdLast?(mdLast.innerText||'').slice(0,60):null,
  mdLegacyLen: mdLegacy?(mdLegacy.textContent||'').length:0,
  rawLen: last?(last.innerText||'').length:0,
  turnState: turnState,
  allTurnStates: allTurnStates,
  copyNear: copyNear,
  copyTotal: cp.length,
  stop: q('button[aria-label*="Stop" i]').length,
  url: (location.href||'').split('/c/')[1] ? location.href.split('/c/')[1].split('/')[0].slice(0,40) : 'no-conv'
 };
})()
"""


async def main():
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    t0 = time.time()
    while time.time() - t0 < dur:
        try:
            t = tabs()
            p = next((x for x in t if x.get("type") == "page" and "chatgpt" in (x.get("url") or "")), None)
            if not p:
                await asyncio.sleep(1); continue
            async with websockets.connect(p["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as ws:
                d = await ev(ws, JS, 1)
            print("[%5.1f] %s" % (time.time() - t0, json.dumps(d, ensure_ascii=False)), flush=True)
        except Exception as e:
            print("ERR", e, flush=True)
        await asyncio.sleep(1.0)


asyncio.run(main())
