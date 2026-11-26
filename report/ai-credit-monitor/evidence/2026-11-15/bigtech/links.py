import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-15/bigtech')
us={'anthropic_axios_link': 'https://news.google.com/rss/articles/CBMidEFVX3lxTE1sUGk1c25oSHF3Vm13T3MwOVlrM2NnYzhrTnhCTjZaTHdOWURwVmlKTTJpZDhta2VtYmRTQVZrM01Qc3B5U1J3clZLZEdzV2REYXJMQWR0QTZEeWptRWljQWFCNkRCanJianRnU0IyYUZfbWhx?oc=5', 'anthropic_mixup_link': 'https://news.google.com/rss/articles/CBMib0FVX3lxTE9nRXk2Q3pSVlhWWWR6dTYzRXlXQzZscnRYZ3d0ZjBHVWxXaU1aQUdFN3NvVERNaW82X0VJMkctbHRiMjM3VzctSk5jZGRieFdFMnJfUGNSOTJWcEpmamJhb0RRcmRmOEhqbVNKNFNuTQ?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'discovery_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
