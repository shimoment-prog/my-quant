import json,re,datetime,urllib.request,concurrent.futures,html
from pathlib import Path
p=Path(__file__).parent
jobs={
'nvda_8k':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000088/nvda-20261117.htm',
'nvda_index':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000088/index.json',
'aaoi_8k':'https://www.sec.gov/Archives/edgar/data/1158114/000110465926129055/tm2629531d2_8k.htm',
'aaoi_index':'https://www.sec.gov/Archives/edgar/data/1158114/000110465926129055/index.json',
'jpm_8k':'https://www.sec.gov/Archives/edgar/data/19617/000001961726000407/jpm-20261117.htm',
'rowan_ir':'https://www.rowan.digital/news',
'athene_ir':'https://ir.athene.com/news-events/press-releases',
'westbank_news':'https://westbankcorp.com/news',
}
def f(e):
 n,u=e;r={'name':n,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Public research analyst research@example.com' if 'sec.gov' in u else 'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=18) as h:d=h.read();r['final_url']=h.url
  (p/(n+('.json' if n.endswith('_index') else '.html'))).write_bytes(d)
  t=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',d.decode('utf8','replace'),flags=re.I|re.S)));t=re.sub(r'\s+',' ',t);(p/(n+'.txt')).write_text(t);r.update(ok=True,chars=len(t),text=t[:25000])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(f,jobs.items()))
(p/'follow_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
