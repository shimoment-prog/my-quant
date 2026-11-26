import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,re,html,xml.etree.ElementTree as ET
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-10/priority')
urls={'bing_latimes':'https://www.bing.com/search?format=rss&q='+urllib.parse.quote('site:latimes.com "OpenAI closes latest funding round"'),'latimes_rss':'https://www.latimes.com/business/rss2.0.xml'}
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+'.xml')).write_bytes(b)
  try:d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link','description']} for el in ET.fromstring(b).findall('.//item')][:25]
  except Exception:d['text']=b.decode(errors='replace')[:1500]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=2).map(lambda kv:get(*kv),urls.items()));(p/'openai_follow_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
