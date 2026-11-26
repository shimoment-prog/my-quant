import json,concurrent.futures,datetime,urllib.request,urllib.parse,xml.etree.ElementTree as ET,html,re
from pathlib import Path
p=Path(__file__).parent
qs={'optical':'2026年11月16日 新易盛 中际旭创 订单 1.6T when:2d','battery':'2026年11月16日 宁德时代 龙蟠 订单 when:2d','memory':'2026年11月16日 兆易创新 存储 芯片 when:2d','liquor':'2026年11月16日 贵州茅台 五粮液 批价 when:2d'}
def run(x):
 n,q=x;u='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans';r={'name':n,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  z=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=18).read();(p/'raw'/(n+'.xml')).write_bytes(z);x=ET.fromstring(z);r.update(ok=True,items=[{k:i.findtext(k) for k in ('title','link','pubDate','source')} for i in x.findall('./channel/item')][:15])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:r=list(e.map(run,qs.items()))
(p/'raw'/'news_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
