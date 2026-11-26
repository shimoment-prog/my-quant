import json,urllib.request,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
b=Path('/private/tmp/ai-credit-monitor-2026-11-07/chain')
items={'wulf_10q':'https://www.sec.gov/Archives/edgar/data/1083301/000162828026071671/wulf-20260930.htm','wulf_8k':'https://www.sec.gov/Archives/edgar/data/1083301/000162828026071306/wulf-20261106.htm','wulf_index':'https://www.sec.gov/Archives/edgar/data/1083301/000162828026071306/index.json','blackstone_10q':'https://www.sec.gov/Archives/edgar/data/1393818/000119312526451802/d179995d10q.htm','ares_10q':'https://www.sec.gov/Archives/edgar/data/1176948/000162828026071628/ares-20260930.htm'}
def fetch(z):
 k,u=z
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Public research analyst research@example.com'}),timeout=30) as f:d=f.read()
  (b/(k+'.html')).write_bytes(d)
  if k.endswith('index'):(b/(k+'.json')).write_bytes(d)
  else:
   soup=BeautifulSoup(d,'html.parser');[t.decompose() for t in soup.find_all(['script','style'])];(b/(k+'.txt')).write_text(soup.get_text(' ',strip=True))
  return dict(name=k,url=u,ok=True,bytes=len(d))
 except Exception as e:return dict(name=k,url=u,ok=False,error=str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(fetch,items.items()))
(b/'document_manifest.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
