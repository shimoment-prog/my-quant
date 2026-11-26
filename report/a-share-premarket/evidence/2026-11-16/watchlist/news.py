import json,urllib.request,urllib.parse,concurrent.futures,xml.etree.ElementTree as ET,datetime
from pathlib import Path
b=Path(__file__).parent / "raw"
qs={"optical":"(新易盛 OR 中际旭创) (公告 OR 美国 OR 订单 OR 光模块) when:3d","catl":"宁德时代 (公告 OR 出口 OR 合同 OR 召回 OR 订单 OR 锂) when:3d","liquor":"(五粮液 OR 贵州茅台) (公告 OR 分红 OR 批价 OR 政策) when:3d","gigadevice":"兆易创新 (公告 OR 存储 OR 订单) when:3d"}
def fetch(z):
 k,q=z;u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=zh-CN&gl=CN&ceid=CN:zh-Hans";r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as f:d=f.read()
  (b/(k+".xml")).write_bytes(d);x=ET.fromstring(d);r["items"]=[{v:i.findtext(v) for v in ["title","link","pubDate","source"]} for i in x.findall("./channel/item")][:30];r["ok"]=True
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:out=list(ex.map(fetch,qs.items()))
(b/"news_manifest.json").write_text(json.dumps(out,indent=2))
for x in out:print(json.dumps(x))
