import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-13/bigtech')
us={'asia_reuters_link': 'https://news.google.com/rss/articles/CBMizgFBVV95cUxQSkZJZGdvOEZWNkZuZ3pSWXU4QUktR01VVWpXc1I3OWtjQnFYaEtRMHVjdUJCblRxdDh2Wm0tbmJQN0gtWVN6b3dnVFlMVGM1Qk8ydHgtb0tndU5xblJGOTVxRWFFYjdjdDJIQkcwckZqMnNDUkZlNE56dzVGd0dMMVFaZUMydjZPaTVkcmRGQU1sZXlscUx0UkRINlpVZk9QYXFiZElNSlc1cG5JTHYwTVplbzM5b0FLOHZLelZZWnlxcGpEdEstNi0zSFprUQ?oc=5', 'asia_cod_link': 'https://news.google.com/rss/articles/CBMihgJBVV95cUxPUTYzemJoOGxYbGxWLVZEVUZTSDIxU09pS0Z2WlRhSjg3OUNRd0taUGJsMkE4QTFHa3hVaC12bE92TnE1ekFyV2M1Y1liOTRVaVh5aVptcVhoRERtQVplelBOM0ozejBlQ2tlSm1ER2EwSmt1MWtlSlJaVDdRTFc4RmtDYTJPVURvdUEtV1FYTkxCSGhxcmpQanJ0Y0pxa0JwN2FsWXVxUWxqajc5RHdoZk9lSnVFdURDS0VHUE9fTjFxRGNNVlo5YWJwUDVNdkRaYzFENUtad0ZHSFktSXhDTC1zMnVrX243RzJLNnVPOHNpZUg2Q3E2WEpPUFZUaFl4VjRmc1pn?oc=5', 'asia_quartz_link': 'https://news.google.com/rss/articles/CBMieEFVX3lxTFA0T1FpUnlpWkpabjJpbFlsdkZpd1drVmxicXlRVFQ4OG55OXZOcXNvV0lwTmlxdmdEa3RIc01sT1BSNWkzb1JYbTM0RGJqdGRhUUdWbTZSQ0t1Q1F4YWh5d1o0Mks5N0xSZ1BvRVlmaTFkMmo3NEViMw?oc=5', 'asia_standard_link': 'https://news.google.com/rss/articles/CBMi1gFBVV95cUxOODQ3WWpoZi1vMTFGbU9SNWZKdWdqOHNQemRDMElGYWFLOGJaeEZQSHYzX3hlazRfQXpGbkVEOU9YQUNBRnZxWk9ZY1R2NjRtUUpMd0NjaFJmNWtzbWVJV1VzYXdvT2ZpLXZOTkJWOGFTZU9kcDNtZ2FDSUJJVUV5anNlc0UyY0hfX1dqMkxrRlVXVmtfUDVOTGZXZGdqdE1QN3dELXNYRDQwOXpIc0NrcG9XejV4RlNkVXlnb0NjOFNwcFdyNlNNbXBmQ2ZYVUM3Z1Y1VHVB?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'asia_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
