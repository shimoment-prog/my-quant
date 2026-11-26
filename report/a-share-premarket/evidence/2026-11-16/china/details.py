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
urls={'ce_page1':'https://finance.ce.cn/stock/gsgdbd/index_1.shtml','ce_page2':'https://finance.ce.cn/stock/gsgdbd/index_2.shtml','csrc_speech':'http://www.csrc.gov.cn/csrc/c106311/c7670983/content.shtml','pbc_finance':'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026111315073060062/index.html','cls_weekend':'https://www.cls.cn/detail/2534675','cls_morning':'https://www.cls.cn/detail/2534816'}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:r=list(ex.map(get,urls.items()))
(b/'details_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
