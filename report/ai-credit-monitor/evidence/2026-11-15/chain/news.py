import json,urllib.request,urllib.parse,concurrent.futures,xml.etree.ElementTree as ET,datetime
from pathlib import Path
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-15/chain")
qs={"suppliers":"(AAOI OR Coherent OR Lumentum OR Marvell OR Fabrinet OR Ciena) (revenue OR guidance OR outlook) when:1d","iren":"(IREN OR TeraWulf) (Microsoft OR Anthropic OR funding OR cancel OR refund OR delivery) when:1d","nebius":"Nebius (Q3 OR delay OR outlook OR capacity OR financing) when:5d","lenders":"(Apollo OR Blackstone OR Ares OR JPMorgan) (AI OR datacenter OR \"data center\") when:1d"}
def fetch(z):
 k,q=z;u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en";r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as f:d=f.read()
  (b/(k+".xml")).write_bytes(d);x=ET.fromstring(d);r["items"]=[{v:i.findtext(v) for v in ["title","link","pubDate","source"]} for i in x.findall("./channel/item")][:30];r["ok"]=True
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:out=list(ex.map(fetch,qs.items()))
(b/"news_manifest.json").write_text(json.dumps(out,indent=2))
for x in out:print(json.dumps(x))
