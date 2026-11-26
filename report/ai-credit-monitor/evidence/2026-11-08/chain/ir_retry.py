import concurrent.futures,datetime,json,urllib.request
from pathlib import Path
from html import unescape
import re
b=Path('/private/tmp/ai-credit-monitor-2026-11-08/chain')
urls={
 'iren_ir_news_retry':'https://iren.gcs-web.com/news-releases',
 'terawulf_ir_news_retry':'https://investors.terawulf.com/news-events/press-releases',
}
def f(z):
 k,u=z;r={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=15) as h: s=h.read();r['final_url']=h.url
  (b/(k+'.html')).write_bytes(s)
  t=s.decode('utf-8','replace');t=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',t,flags=re.S|re.I)
  t=unescape(re.sub(r'<[^>]+>',' ',t));t=re.sub(r'\s+',' ',t)
  (b/(k+'.txt')).write_text(t)
  pats=['November 7','November 8','Nov 7','Nov. 7','November 6','November 5','2026']
  positions=sorted(set(m.start() for p in pats for m in list(re.finditer(re.escape(p),t))[:20]))
  r.update(ok=True,date_context=[t[max(0,i-90):i+220] for i in positions[:24]])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:rs=list(ex.map(f,urls.items()))
(b/'ir_retry_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
