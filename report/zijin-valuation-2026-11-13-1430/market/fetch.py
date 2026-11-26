import concurrent.futures as cf,datetime as dt,json,pathlib,urllib.request
P=pathlib.Path('/tmp/zijin-valuation-20261113/market')
urls={
'quotes':'https://qt.gtimg.cn/q=sh601899,hk02899,sh000001,sh600547,sh600362,sh603993,sh600988,sh518880,sh512400,sz399006',
'sina':'https://hq.sinajs.cn/list=sh601899,rt_hk02899,sh000001,sh600547,sh600362,sh603993,sh600988,sh518880,sh512400,sz399006,fx_shkdcny',
'daily':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh601899,day,,,180,qfq',
'five_min':'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol=sh601899&scale=5&ma=no&datalen=100',
}
def f(it):
 n,u=it;r=dict(id=n,url=u,started_at=dt.datetime.now(dt.timezone.utc).isoformat())
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
  with urllib.request.urlopen(req,timeout=18) as z:b=z.read()
  (P/(n+'.raw')).write_bytes(b);r.update(ok=True,bytes=len(b),retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with cf.ThreadPoolExecutor(max_workers=4) as ex:rs=list(ex.map(f,urls.items()))
(P/'manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(r)
