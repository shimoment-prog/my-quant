import json,urllib.request,urllib.parse,concurrent.futures,datetime,xml.etree.ElementTree as ET
from pathlib import Path
import re, html
def clean(s):
 return html.unescape(re.sub(r"<[^>]+>"," ",s))
b=Path('/private/tmp/a-share-premarket-2026-11-09/china')
qs={'close':'2026年11月6日 A股 收评 成交额 上涨 下跌','policy':'2026年11月8日 央行 证监会 国务院 政策 when:3d'}
urls={'tencent':'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000300','sse':'https://www.sse.com.cn/disclosure/dealinstruc/closed/','szse':'https://www.szse.cn/','pbc':'http://www.pbc.gov.cn/','csrc':'http://www.csrc.gov.cn/','gov':'https://www.gov.cn/'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans' for k,q in qs.items()})
def get(z):
 k,u=z;r=dict(name=k,url=u,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=20) as f:d=f.read()
  (b/(k+'.html')).write_bytes(d);s=d.decode('gb18030' if k=='tencent' else 'utf-8',errors='replace');(b/(k+'.txt')).write_text(clean(s));r.update(ok=True,bytes=len(d))
  if k in qs:
   x=ET.fromstring(d);r['items']=[{v:i.findtext(v) for v in ['title','link','pubDate','source']} for i in x.findall('./channel/item')][:40]
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:r=list(ex.map(get,urls.items()))
(b/'manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
