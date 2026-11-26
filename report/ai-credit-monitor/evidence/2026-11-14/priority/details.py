import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-14/priority')
urls={
'coreweave_semafor':'https://www.semafor.com/article/11/13/2026/coreweave-tunes-out-nvidia-noise-looks-to-raise-4b',
'openai_dataconomy':'https://dataconomy.com/2026/11/13/openai-raises-15-billion-at-1-25-trillion-valuation/',
'openai_techfundingnews':'https://techfundingnews.com/openai-reportedly-raises-15b-at-1-25t-valuation-as-anthropic-ipo-approaches/',
'openai_247':'https://247wallst.com/investing/2026/11/13/openai-raised-only-15-billion-half-what-it-wanted/',
'openai_techcentral':'https://www.techcentral.ie/openai-sees-quarterly-revenue-rise-by-nearly-50-to-10bn/'
}
for k,q in {'bing_cnbc':'site:cnbc.com/2026/11/ OpenAI raises 15 billion 1.25 trillion','bing_openai_q3':'OpenAI 2026 November 13 revenue 10 billion loss 11 billion','bing_coreweave':'CoreWeave tunes out Nvidia noise looks to raise 4B Semafor'}.items(): urls[k]='https://www.bing.com/search?format=rss&q='+urllib.parse.quote(q)
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,final_url=r.url,bytes=len(b));(p/(k+('.xml' if k.startswith('bing_') else '.html'))).write_bytes(b)
  s=b.decode(errors='replace');d['canonical']=re.findall(r'<link[^>]*rel=["\']canonical["\'][^>]*>',s);d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);d['links']=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',s) if any(t in x for t in ['cnbc.com','bloomberg.com','ft.com','theinformation.com'])];s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:27000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'details_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,ensure_ascii=False,indent=2))
