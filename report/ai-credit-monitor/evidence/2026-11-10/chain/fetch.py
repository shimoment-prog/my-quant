import json,concurrent.futures,datetime,urllib.request
from pathlib import Path
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-10/chain")
items={"jpmorgan":"0000019617","apollo":"0001858681","blackstone":"0001393818","ares":"0001176948","iren":"0001878848","terawulf":"0001083301","nvda":"0001045810","amd":"0000002488","mrvl":"0001835632","lite":"0001633978","cohr":"0000820318","aaoi":"0001158114","fn":"0001408710","cien":"0000936395"}
cut="2026-11-09T00:35:19.758136"
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(k,c):
 u="https://data.sec.gov/submissions/CIK"+c+".json"
 r={"company":k,"cik":c,"url":u,"retrieved_at":now}
 try:
  req=urllib.request.Request(u,headers={"User-Agent":"Public research analyst contact research@example.com"})
  with urllib.request.urlopen(req,timeout=20) as f:data=f.read()
  (b/(k+"_submissions.json")).write_bytes(data)
  d=json.loads(data);x=d["filings"]["recent"];rows=[]
  for i,a in enumerate(x["accessionNumber"]):
   t=x.get("acceptanceDateTime",[""]*len(x["accessionNumber"]))[i]
   if t>cut:
    rows.append({q:x.get(q,[""]*len(x["accessionNumber"]))[i] for q in ["accessionNumber","form","filingDate","acceptanceDateTime","primaryDocument","items"]})
  r.update(ok=True,new_filings=rows,latest10q=[{q:x[q][i] for q in ["accessionNumber","form","filingDate","acceptanceDateTime","primaryDocument"]} for i,f in enumerate(x["form"]) if f=="10-Q"][:1])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=list(ex.map(lambda z:get(*z),items.items()))
(b/"submission_manifest.json").write_text(json.dumps(out,indent=2))
for r in out:
 print(json.dumps({**{k:v for k,v in r.items() if k!="new_filings"},"new_relevant_filings":[x for x in r.get("new_filings",[]) if x["form"] in ["8-K","10-Q","10-K","6-K"]],"new_all_count":len(r.get("new_filings",[]))}))
