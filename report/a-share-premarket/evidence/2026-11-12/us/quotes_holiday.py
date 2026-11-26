import urllib.request,pathlib,datetime,json,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/a-share-premarket-2026-11-12/us')
jobs={'sina_us':'https://hq.sinajs.cn/list=gb_sox,gb_nvda,gb_crwv,gb_csco,gb_avgo,gb_amd,gb_lite,gb_mrvl,gb_cohr,gb_aaoi,gb_fn,gb_cien','NYSE_calendar':'https://www.nyse.com/markets/hours-calendars','SIFMA_calendar':'https://www.sifma.org/resources/general/holiday-schedule/'}
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=20).read();(p/(n+('.txt' if n=='sina_us' else '.html'))).write_bytes(raw)
  s=raw.decode('gb18030' if n=='sina_us' else 'utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(f,jobs.items()));(p/'quotes_holiday_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
if(p/'sina_us_clean.txt').exists():print((p/'sina_us_clean.txt').read_text())
