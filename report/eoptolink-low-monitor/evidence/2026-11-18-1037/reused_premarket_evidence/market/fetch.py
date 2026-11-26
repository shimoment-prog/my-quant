import concurrent.futures as cf,datetime as dt,json,pathlib,urllib.request
P=pathlib.Path('/private/tmp/optics-nov18-market')
urls={
'quotes':'https://qt.gtimg.cn/q=usLITE,usMRVL,usCOHR,usCIEN,usAAOI,usFN,usNVDA,usAVGO,us.IXIC,usSOXX',
'sina':'https://hq.sinajs.cn/list=gb_lite,gb_mrvl,gb_cohr,gb_cien,gb_aaoi,gb_fn,gb_nvda,gb_avgo,gb_sox,gb_ixic',
'nasdaq_index':'https://qt.gtimg.cn/q=us.IXIC,us.IXIC,usSOX,usSOXX,usNDX',
}
for s in ['LITE','MRVL','COHR','CIEN','AAOI','FN']:
 urls['history_'+s]='https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param=us'+s+',day,,,40,qfq'
def fetch(item):
 name,url=item;r={'id':name,'url':url,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
  with urllib.request.urlopen(req,timeout=18) as z:b=z.read()
  (P/(name+'.raw')).write_bytes(b);r.update(ok=True,length=len(b),retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with cf.ThreadPoolExecutor(max_workers=8) as pool:rs=list(pool.map(fetch,urls.items()))
(P/'manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(r)
