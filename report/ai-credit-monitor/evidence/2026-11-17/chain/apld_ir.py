import concurrent.futures,datetime,json,urllib.request
from pathlib import Path
from html import unescape
import re
b=Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-17/chain')
urls={'apld_ir':'https://ir.applieddigital.com/news-events/press-releases'}
def f(z):
 k,u=z;r={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=15) as h: s=h.read();r['final_url']=h.url
  (b/(k+'.html')).write_bytes(s)
  t=s.decode('utf-8','replace');t=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',t,flags=re.S|re.I)
  t=unescape(re.sub(r'<[^>]+>',' ',t));t=re.sub(r'\s+',' ',t)
  (b/(k+'.txt')).write_text(t)
  pats=['November 9','November 10','Nov 9','Nov. 9','2026']
  positions=sorted(set(m.start() for p in pats for m in list(re.finditer(re.escape(p),t))[:20]))
  r.update(ok=True,date_context=[t[max(0,i-90):i+220] for i in positions[:24]])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:rs=list(ex.map(f,urls.items()))
(b/'apld_ir_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
