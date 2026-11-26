import json,urllib.request,urllib.parse,concurrent.futures,datetime,xml.etree.ElementTree as ET
from pathlib import Path
import re, html
def clean(s):
 return html.unescape(re.sub(r"<[^>]+>"," ",s))
b=Path('/Users/richao11/myproject/my-quant/report/a-share-premarket/evidence/2026-11-16/china')
def get(z):
 k,u=z;r=dict(name=k,url=u,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=20) as f:d=f.read()
  (b/(k+'.html')).write_bytes(d);s=d.decode('gb18030' if k=='tencent' else 'utf-8',errors='replace');(b/(k+'.txt')).write_text(clean(s));r.update(ok=True,bytes=len(d))
  if k in qs:
   x=ET.fromstring(d);r['items']=[{v:i.findtext(v) for v in ['title','link','pubDate','source']} for i in x.findall('./channel/item')][:40]
 except Exception as e:r.update(ok=False,error=str(e))
 return r


qs={}
urls={'ce_close':'https://finance.ce.cn/stock/gsgdbd/202611/t20261113_3293818.shtml','nhsa':'https://www.nhsa.gov.cn/','mofcom':'https://www.mofcom.gov.cn/','stats':'https://www.stats.gov.cn/','scio':'https://www.scio.gov.cn/'}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(get,urls.items()))
(b/'followup_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
