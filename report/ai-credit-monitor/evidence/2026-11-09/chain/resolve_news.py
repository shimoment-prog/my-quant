import json,urllib.request,datetime,concurrent.futures,re,html
from pathlib import Path
b=Path('/private/tmp/ai-credit-monitor-2026-11-09/chain');d=json.loads((b/'news_manifest.json').read_text());g={r['name']:r['items'] for r in d}
items={'spacex_article':g['lenders'][6], 'anthropic_article':g['ai_chain'][11], 'jpm_article':g['lenders'][1]}
def f(z):
 k,x=z;u=x['link'];r={'name':k,**x,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=15) as h:s=h.read().decode('utf8','replace');r['final_url']=h.url
  (b/(k+'.html')).write_text(s)
  r.update(ok=True,external_links=list(dict.fromkeys(html.unescape(i) for i in re.findall(r'href="(https?[^\"]+)"',s) if not any(p in i for p in ['google.com','gstatic.com','googleapis.com']))))
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rs=list(ex.map(f,items.items()))
(b/'resolve_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
