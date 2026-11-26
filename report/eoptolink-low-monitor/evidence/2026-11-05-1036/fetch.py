import concurrent.futures as cf
import datetime as dt
import json
import pathlib
import urllib.request

ROOT=pathlib.Path('/tmp/eoptolink-monitor-20261105-1030')
ROOT.mkdir(exist_ok=True)
urls={
 'quotes.txt':'https://qt.gtimg.cn/q=sz300502,sz300308,sh515880,sz399006,sh000001',
 'sina.txt':'https://hq.sinajs.cn/list=sz300502,sz300308,sh515880,sz399006',
 'minute.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sz300502',
 'minute_peer.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sz300308',
 'minute_etf.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh515880',
 'm5_ohlc.txt':'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol=sz300502&scale=5&ma=no&datalen=120',
 'history.json':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz300502,day,,,120,qfq',
 'sina_announcements.html':'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/300502.phtml',
 'announcements.json':'https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=10&page_index=1&ann_type=A&client_source=web&stock_list=300502',
}

def fetch(job):
 name,url=job
 result={'name':name,'url':url,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
  with urllib.request.urlopen(req,timeout=15) as response:
   raw=response.read()
  (ROOT/name).write_bytes(raw)
  result.update(ok=True,bytes=len(raw),retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
 except Exception as exc:
  result.update(ok=False,error=str(exc))
 return result

with cf.ThreadPoolExecutor(max_workers=6) as pool:
 manifest=list(pool.map(fetch,urls.items()))
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
for row in manifest:
 print(row)
