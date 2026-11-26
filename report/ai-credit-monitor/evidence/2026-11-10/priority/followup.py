import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-10/priority')
urls={
 'search_cnbc':'https://www.google.com/search?q='+urllib.parse.quote('site:cnbc.com/2026/11/09/ CoreWeave doom cycle neocloud credit'),
 'search_latimes':'https://www.google.com/search?q='+urllib.parse.quote('site:latimes.com 2026-11-09 OpenAI closes latest funding'),
 'openai_news':'https://openai.com/news/rss.xml',
 'cnbc_tech_rss':'https://www.cnbc.com/id/19854910/device/rss/rss.html',
}
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,application/xml,*/*'}),timeout=18);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+('.xml' if 'rss' in k or k=='openai_news' else '.html'))).write_bytes(b)
  s=b.decode(errors='replace')
  if 'rss' in k or k=='openai_news':d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link']} for el in ET.fromstring(b).findall('.//item')][:35]
  else:
   d['urls']=list(dict.fromkeys(re.findall(r'https?[^\s<>"&]+',html.unescape(s))))[:80]
   s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:12000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(lambda kv:get(*kv),urls.items()));(p/'followup_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
