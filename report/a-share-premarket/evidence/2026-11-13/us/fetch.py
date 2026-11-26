import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,re,html,xml.etree.ElementTree as E
p=pathlib.Path('/private/tmp/a-share-premarket-2026-11-13/us')
jobs={'cnbc_close':'https://www.cnbc.com/2026/11/11/stock-market-today-live-updates.html','cnbc_close_alt':'https://www.cnbc.com/2026/11/12/stock-market-today-live-updates.html'}
queries={'news_market':'US stock market November 12 2026 S&P Nasdaq Dow Reuters CNBC','news_optical':'Cisco CoreWeave Lumentum Coherent Marvell November 12 2026 earnings','news_macro':'Treasury yields dollar oil November 12 2026 Reuters CNBC'}
for n,q in queries.items():jobs[n]='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+('.xml' if n.startswith('news') else '.html'))).write_bytes(raw)
  s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,jobs.items()));(p/'manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
for n in queries:
 try:
  z=E.fromstring((p/(n+'.xml')).read_bytes());print('\nNEWS',n)
  for i in z.findall('./channel/item')[:10]:print(i.findtext('pubDate'),i.findtext('title'),i.findtext('link'))
 except:pass
