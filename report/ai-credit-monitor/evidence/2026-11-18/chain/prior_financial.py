import json,re,datetime,urllib.request,concurrent.futures,html
from pathlib import Path
p=Path(__file__).parent
jobs={
'nvda_q2_pr':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27pr.htm',
'nvda_q2_cfo':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27cfocommentary.htm',
'rowan_home':'https://www.rowan.digital/',
'phononic_trinity':'https://www.trinitycapital.com/press-releases/trinity-capital-inc-provides-100-million-growth-capital-to-phononic/'
}

def f(e):
 n,u=e;r={'name':n,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Public research analyst research@example.com' if 'sec.gov' in u else 'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=18) as h:d=h.read();r['final_url']=h.url
  (p/(n+('.json' if n.endswith('_index') else '.html'))).write_bytes(d)
  t=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',d.decode('utf8','replace'),flags=re.I|re.S)));t=re.sub(r'\s+',' ',t);(p/(n+'.txt')).write_text(t);r.update(ok=True,chars=len(t),text=t[:55000])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(f,jobs.items()))
(p/'prior_financial_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
