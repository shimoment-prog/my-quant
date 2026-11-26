import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,re,html,xml.etree.ElementTree as E
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/a-share-premarket/evidence/2026-11-16/us')
qs={'oil_search':'oil prices November 13 2026 Brent WTI Reuters settlement after:2026-11-13 before:2026-11-15','amat_search':'Applied Materials fiscal fourth quarter 2026 results November 12 2026 investor','nvda_search':'NVIDIA financial results November 17 2026 Tuesday investor relations','ppi_search':'October 2026 PPI November 13 2026 6.5 0.3'}
jobs={n:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for n,q in qs.items()}
jobs['amat_ir']='https://ir.appliedmaterials.com/news-releases/news-release-details/2026/Applied-Materials-Announces-Fourth-Quarter-and-Fiscal-Year-2026-Results/default.aspx'
jobs['nvidia_ir']='https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Third-Quarter-Fiscal-2027/default.aspx'
def f(job):
 n,u=job;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read();(p/(n+('.xml' if n in qs else '.html'))).write_bytes(raw)
  s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'_clean.txt')).write_text(s)
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'len':len(raw)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(f,jobs.items()));(p/'followup_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
for n in qs:
 try:
  z=E.fromstring((p/(n+'.xml')).read_bytes());print('\nNEWS',n)
  for i in z.findall('./channel/item')[:8]:print(i.findtext('pubDate'),i.findtext('title'),i.findtext('link'))
 except:pass
