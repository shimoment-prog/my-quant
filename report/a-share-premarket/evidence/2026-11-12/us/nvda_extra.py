import urllib.request,pathlib,datetime,json,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/a-share-premarket-2026-11-12/us')
jobs={'cnbc_nvda_late':'https://www.cnbc.com/2026/11/11/nvidia-jensen-huang-affair-employee.html','NVDA_newsroom':'https://nvidianews.nvidia.com/','NVDA_independent_prior':'https://nvidianews.nvidia.com/news/statement-from-the-independent-members-of-the-nvidia-board','SIFMA_new':'https://www.sifma.org/resources/general/holiday-schedule','cnbc_future_quote':'https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=@ND.1&output=json'}
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cnbc.com/'}),timeout=20).read();(p/(n+'.html')).write_bytes(raw)
  s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,jobs.items()));(p/'nvda_extra_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
