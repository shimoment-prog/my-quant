import urllib.request,json,datetime,concurrent.futures
from pathlib import Path
p=Path(__file__).parent
items={'longpan_page2':'https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code=AN202611161831737873&client_source=web&page_index=2'}
def fetch(z):
 k,u=z;r={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as h:d=h.read()
  (p/'raw'/(k+'_content.json')).write_bytes(d);j=json.loads(d);r.update(ok=True,data=j)
 except Exception as e:r.update(ok=False,error=str(e))
 return r
rs=list(map(fetch,items.items()));(p/'raw'/'content_page2_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
