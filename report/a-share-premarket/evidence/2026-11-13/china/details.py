import json,urllib.request,urllib.parse,concurrent.futures,datetime,xml.etree.ElementTree as ET
from pathlib import Path
import re, html
def clean(s):
 return html.unescape(re.sub(r"<[^>]+>"," ",s))
b=Path('/Users/richao11/myproject/my-quant/report/a-share-premarket/evidence/2026-11-13/china')
qs={'close':'2026年11月12日 A股 收评 成交额 上涨 下跌','policy':'2026年11月12日 央行 证监会 国务院 政策 when:2d'}
urls={'sse':'https://www.sse.com.cn/disclosure/dealinstruc/closed/','szse':'https://www.szse.cn/','pbc':'http://www.pbc.gov.cn/','csrc':'http://www.csrc.gov.cn/','gov':'https://www.gov.cn/','sse_home':'https://www.sse.com.cn/','szse_notice':'https://www.szse.cn/disclosure/notice/general/index.html','ce':'https://finance.ce.cn/stock/gsgdbd/','cls':'https://www.cls.cn/'}
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

qs={}
urls={'ce_close':'https://finance.ce.cn/stock/gsgdbd/202611/t20261112_3292693.shtml','ce_csrc':'https://finance.ce.cn/stock/gsgdbd/202611/t20261112_3292703.shtml','ce_csrc2':'https://finance.ce.cn/stock/gsgdbd/202611/t20261113_3293194.shtml','cls_morning':'https://www.cls.cn/detail/2533284','pbc_omo':'http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026111208502561107/index.html'}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(get,urls.items()))
(b/'details_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
