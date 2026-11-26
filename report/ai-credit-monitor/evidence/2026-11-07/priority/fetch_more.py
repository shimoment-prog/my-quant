import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-07/priority')
urls={'coreweave_bond_cnbc':'https://www.cnbc.com/2026/11/06/coreweave-bond-yield-ai-credit.html','ing_cnbc':'https://www.cnbc.com/2026/11/06/ing-data-center-loans-ai-debt.html'}
qs={'news_coreweave_wide':'CoreWeave (bonds OR debt OR CDS OR financing OR guidance) when:1d','news_oracle_wide':'Oracle (bonds OR debt OR CDS OR financing OR capex) when:1d','news_cnbc_exact':'"The AI" "credit card" "CoreWeave"','news_ing_exact':'"ING puts" "data-center loans"'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for k,q in qs.items()})
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20);b=r.read();d.update(status=r.status,bytes=len(b),final_url=r.url);(p/(k+('.xml' if k.startswith('news_') else '.html'))).write_bytes(b)
  if k.startswith('news_'):d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link']} for el in ET.fromstring(b).findall('.//item')][:18]
  else:
   s=b.decode(errors='replace');s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:20000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'additional_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
