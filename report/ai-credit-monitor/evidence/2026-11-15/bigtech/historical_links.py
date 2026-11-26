import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-15/bigtech')
us={'meta_old_reuters_link': 'https://news.google.com/rss/articles/CBMirwFBVV95cUxNRU1kYi03WEJLMjUzY0lVVHVwekxGWTUzVVdZTDFGTFFKVlZERWZCOFVyak1KZ3VUYzlBZzdxZS11SW1Ldzc1amZqeG41TFJ4V0FQSW9pWFEycWhjeHByMG95SFp5VTk0SFQxYnI4Q3NLR0lZYTRSVXdGbFp6VlM4M1NqdlhZT3QzdC1mSU9ScFQwVU1mSFgxVzJvcDRnU3BIVGF4Nkotblhydno4SUZR?oc=5', 'meta_company_link': 'https://news.google.com/rss/articles/CBMikAFBVV95cUxQNFU5ekVGTG5qMzNDaVJGQVJJVVIxdmpJQmNMUmlJSWtrNllqTlR5UkhublhpSnBNa21naTlCa09UZTIwVWpVRDdpWHFEYm1GbUo3THIxeWYtUllCZDdNUlBrSm93NG1EeEFhd3JtTThrR0c5LTA5eGd5V0c0T2Q0NGN5RmdLbzBUZzFUazRBTGjSAZYBQVVfeXFMTkZWeUhkVTljZERvM2dBdzlFRWhEMWJwSWw5NTB0ZTk5V1RHM2tFb2FiQWJmSmFMV0d6QVBoR2M4TlhkaGQwTU9qYVpIbWk1TlJtOGZIeF9xd0VjeWVTYzJENFE2am9lWm93YmNZd1VLS0dsaGpDSExpbjRycWhqdjBVZFVWeFJpVU1FTFdsY01UWVdJOVNn?oc=5', 'amazon_old_reuters_link': 'https://news.google.com/rss/articles/CBMiuwFBVV95cUxOOWpOQmdFWlB0amVrd0tyTnBaNzdNam8tVVFFdXNUelhWYlhBZDFHbzBPeFk3TnZYUU1UcWxadk9XQVdwb3ZjM1VMWVNiM3hUakRfQUkxWURfdlpKQWFMQ0RfQW0tMXVyeFNldENXcXJRQk02Y1FiZVhFSGFSTzBPamRKQ2FHX0ljN0lXS0p0aThsVVBEUVFfWlZaNVBvX21SYU1LTGNBVEtKeUxxdkpvNS1xVEMzOU8wQ2hz?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'historical_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
