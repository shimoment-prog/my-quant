import urllib.request,pathlib,datetime,json,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/a-share-premarket-2026-11-10/us')
jobs={'nvda_board':'https://nvidianews.nvidia.com/news/statement-from-nvidia-board-of-directors','cnbc_nvda':'https://www.cnbc.com/2026/11/08/nvidia-jensen-huang-email-board-of-directors-statement.html','cnbc_nvda_reaction':'https://www.cnbc.com/2026/11/09/nvidia-jensen-huang-chinese-spy-investigation.html','cnbc_CPI':'https://www.cnbc.com/2026/11/09/october-cpi-report-2026-inflation.html'}
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read();(p/(n+'.html')).write_bytes(raw)
  s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(f,jobs.items()));(p/'extra_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
