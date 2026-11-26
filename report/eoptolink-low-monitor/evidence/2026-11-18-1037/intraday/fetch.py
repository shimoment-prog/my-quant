import concurrent.futures as cf,datetime as dt,json,pathlib,urllib.request
P=pathlib.Path('/private/tmp/eoptolink-monitor-20261118-1030')
urls={'quotes.txt':'https://qt.gtimg.cn/q=sz300502,sz300308,sh515880,sz399006','sina.txt':'https://hq.sinajs.cn/list=sz300502,sz300308,sh515880,sz399006','minute.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sz300502','minute_peer.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sz300308','minute_etf.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh515880','m5.txt':'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol=sz300502&scale=5&ma=no&datalen=120','announcements.html':'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/300502.phtml'}
def fetch(x):
 n,u=x;start=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=15) as r:b=r.read()
  (P/n).write_bytes(b);return {'name':n,'url':u,'ok':True,'bytes':len(b),'retrieved_at':dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),'started_at':start}
 except Exception as e:return {'name':n,'url':u,'ok':False,'error':str(e),'started_at':start}
with cf.ThreadPoolExecutor(max_workers=8) as pool:out=list(pool.map(fetch,urls.items()))
(P/'manifest.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
