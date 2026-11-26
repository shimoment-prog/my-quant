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


qs={'breadth':'2026年11月13日 收评 全市场 超 下跌 个股','breadth2':'2026年11月13日 收评 上涨家 下跌家','cls_close_search':'2026年11月13日 每日收评 创业板 财联社'}
urls={'nhsa_notice':'https://www.nhsa.gov.cn/art/2026/11/14/art_104_23384.html','mofcom_trade':'https://www.mofcom.gov.cn/syxwfb/art/2026/art_6d9023bbcdd04810a810ef2059ecad2f.html'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans' for k,q in qs.items()})
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(get,urls.items()))
(b/'last_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
