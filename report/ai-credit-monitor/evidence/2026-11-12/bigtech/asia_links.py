import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-12/bigtech')
us={'asia_investing_link': 'https://news.google.com/rss/articles/CBMivwFBVV95cUxQei04V3B1bUFGLURyVE4xZnEwSVlhSkdkdXB1MHdjREp2WVFDalVqejNORFRod0VoUXFQejRUS1FrU0RJemtfYVdOX3hmb3NDZmZZUmJZZkh0d1A4cmhxV0o0Mlc3VUxZYnBvNnRIZDF2cWg5VzhPVDVtSlNpZHdGeXNtUTV5M0FhVVd4Ym5aV0FsUElvWV9IQmkzeEE0SDF6R2JVRnYzdmZjNjlDY2NTRHZ4QTl0Mzhjdjh2dXZ6WQ?oc=5', 'asia_reuters_link': 'https://news.google.com/rss/articles/CBMiswFBVV95cUxQekxJWlNsQXlpSG80TzJHMDNiREl6ZC0zWEQ0S0FWVWZPXzJpQk5maC1NTFhXQjIyRmk5QlU1QnFxZ2VHZUNkVUNjOWo4azhLVzlHelE3dFk1UUU3UHllNUdiVzVaODFKSHJEZHQ4Q1d2a0FrLUJiYjM3bUlwZ01wODltVlYyY2YyM3dZV1piYjFmTFRlaVZNcVp3V0RMSlM2SHdPbllBTnQzNllPbGw5YWRERQ?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'asia_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
