from pathlib import Path
import urllib.request,urllib.parse,concurrent.futures,json,datetime,re,html
b=Path('/private/tmp/ai-credit-monitor-2026-11-09/chain')
qs={
 'spacex':'Goldman Apollo talks sell SpaceX 40 billion AI deal Bloomberg November 8 2026 Edge Malaysia',
 'anthropic':'Anthropic 3.4 billion generator deal FT November 8 2026',
 'jpm':'JPMorgan AI buildout new problem November 8 2026 Stocktwits'
}
def f(z):
 k,q=z;u='https://www.bing.com/search?format=rss&q='+urllib.parse.quote(q);r={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=15) as h:s=h.read().decode('utf-8','replace')
  (b/(k+'_bing.xml')).write_text(s)
  t=html.unescape(re.sub(r'<[^>]+>',' ',s));t=re.sub(r'\s+',' ',t)
  (b/(k+'_bing.txt')).write_text(t)
  r.update(ok=True,text=t[:16000],links=re.findall(r'href="([^"]+)"',s)[:100])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rs=list(ex.map(f,qs.items()))
(b/'bing_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
