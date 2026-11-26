from pathlib import Path
import urllib.request,concurrent.futures,json,datetime,re,html
p=Path(__file__).parent
jobs={"fed_FSR_actual_pdf":"https://www.federalreserve.gov/publications/files/financial-stability-report-20261113.pdf"}
def f(it):
 n,u=it;r={"id":n,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=18) as z:b=z.read();r.update(status=z.status,final_url=z.url)
  (p/(n+(".pdf" if n.endswith("pdf") else ".html"))).write_bytes(b);r.update(ok=True,bytes=len(b))
  if not n.endswith("pdf"):
   s=b.decode(errors="replace");s=re.sub(r"<(script|style)\b.*?</\1>","",s,flags=re.S|re.I);s=html.unescape(re.sub("<[^>]+>"," ",s));s=re.sub(r"\s+"," ",s);(p/(n+".txt")).write_text(s)
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(f,jobs.items()))
(p/'fed_manifest.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r,indent=2))
