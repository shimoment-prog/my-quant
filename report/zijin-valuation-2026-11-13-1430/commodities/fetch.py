from pathlib import Path
from urllib.request import urlopen,Request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
p=Path('/tmp/zijin-valuation-20261113-commodities')
urls={'quotes':'https://hq.sinajs.cn/list=hf_GC,hf_HG,hf_CAD,hf_XAU,nf_AU0,nf_CU0,fx_susdcnh,DINIW,gb_tnx', 'cu_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/InnerFuturesNewService.getDailyKLine?symbol=CU0', 'au_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/InnerFuturesNewService.getDailyKLine?symbol=AU0','xau_global_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=XAU','gc_global_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=GC','hg_global_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=HG','cad_global_daily':'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_data=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=CAD','goldpage':'https://finance.sina.com.cn/futures/quotes/XAU.shtml','copperpage':'https://finance.sina.com.cn/futures/quotes/CAD.shtml'}
def fetch(n,u):
 t=datetime.now(timezone.utc).isoformat()
 try:
  r=urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=10);s=r.read();(p/(n+'.txt')).write_text(s.decode('gb18030' if n=='quotes' else 'utf8',errors='replace'))
  return {'name':n,'url':u,'final_url':r.geturl(),'retrieved_at':t,'ok':True,'length':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
with ThreadPoolExecutor(max_workers=8) as ex:rows=[f.result() for f in as_completed([ex.submit(fetch,n,u) for n,u in urls.items()])]
(p/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(json.dumps(rows,ensure_ascii=False,indent=2))
