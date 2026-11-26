import concurrent.futures,datetime,json,urllib.request
from pathlib import Path
from html import unescape
import re
b=Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-18/chain')
urls={
 'nvidia_ir':'https://investor.nvidia.com/news-and-events/press-releases/default.aspx',
 'amd_ir':'https://ir.amd.com/news-events/press-releases',
 'broadcom_ir':'https://investors.broadcom.com/press-releases',
 'marvell_ir':'https://investor.marvell.com/news-events/press-releases',
 'lumentum_ir':'https://investor.lumentum.com/financial-news-releases/default.aspx',
 'coherent_ir':'https://www.coherent.com/news/press-releases',
 'aaoi_ir':'https://investors.ao-inc.com/press-releases',
 'fabrinet_ir':'https://investor.fabrinet.com/press-releases',
 'ciena_ir':'https://investor.ciena.com/news/press-releases'
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
  pats=['November 16','November 15','November 14','November 13','November 12','Nov 16','Nov 15','Nov 14','Nov 13','Nov 12','2026']
  positions=sorted(set(m.start() for p in pats for m in list(re.finditer(re.escape(p),t))[:20]))
  r.update(ok=True,date_context=[t[max(0,i-90):i+220] for i in positions[:24]])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:rs=list(ex.map(f,urls.items()))
(b/'supplier_ir_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
