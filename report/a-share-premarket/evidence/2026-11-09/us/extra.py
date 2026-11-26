import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,re,html,xml.etree.ElementTree as E
p=pathlib.Path('/private/tmp/a-share-premarket-2026-11-09/us')
jobs={'cnbc_jobs':'https://www.cnbc.com/2026/11/06/jobs-report-october-2026.html','news_yields':'https://news.google.com/rss/search?q='+urllib.parse.quote('site:cnbc.com/2026/11/06 Treasury yields payrolls')+'&hl=en-US&gl=US&ceid=US:en','news_oil':'https://news.google.com/rss/search?q='+urllib.parse.quote('site:cnbc.com/2026/11/06 oil prices tumble')+'&hl=en-US&gl=US&ceid=US:en'}
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read();(p/(n+('.xml' if n.startswith('news') else '.html'))).write_bytes(raw)
  s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(f,jobs.items()));(p/'extra_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
for n in ['news_yields','news_oil']:
 try:
  z=E.fromstring((p/(n+'.xml')).read_bytes());print('\nNEWS',n)
  for i in z.findall('./channel/item')[:8]:print(i.findtext('pubDate'),i.findtext('title'),i.findtext('link'))
 except:pass
