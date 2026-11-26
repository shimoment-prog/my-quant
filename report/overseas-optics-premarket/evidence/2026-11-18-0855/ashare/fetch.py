import pathlib,urllib.request,concurrent.futures,json,datetime
r=pathlib.Path('/private/tmp/optics-nov18-ashare');u={}
for sym in ['sz300502','sz300308','sh515880','sz399006']:
 u[sym+'-daily.json']='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param='+sym+',day,,,30,qfq'
 u[sym+'-m5.txt']='https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol='+sym+'&scale=5&ma=no&datalen=100'
def get(x):
 k,url=x;z={'file':k,'url':url,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  b=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=30).read();(r/k).write_bytes(b);z.update(ok=True,bytes=len(b),retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());
  if k.endswith('.pdf'):z['valid_pdf']=b.startswith(b'%PDF')
 except Exception as e:z.update(ok=False,error=str(e))
 return z
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 a=list(ex.map(get,u.items()));(r/'manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
