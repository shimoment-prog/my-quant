import urllib.request,json,datetime,pathlib,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-07/priority')
urls={'coreweave_bond_cnbc':'https://www.cnbc.com/2026/11/06/coreweave-bond-yield-tops-16percent-as-ai-credit-stress-rises.html','ing_cnbc':'https://www.cnbc.com/2026/11/06/ing-ai-data-center-loans-debt.html','microsoft_oracle_cnbc':'https://www.cnbc.com/2026/11/06/microsoft-moves-to-consolidate-its-relationships-with-neoclouds-in-ai.html'}
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+'.html')).write_bytes(b);s=b.decode(errors='replace');
  d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S)
  s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:26000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor().map(lambda kv:get(*kv),urls.items()));(p/'article_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
