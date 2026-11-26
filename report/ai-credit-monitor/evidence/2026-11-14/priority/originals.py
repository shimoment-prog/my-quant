import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-14/priority')
urls={
'openai_cnbc_video':'https://www.cnbc.com/video/2026/11/12/openai-raises-15b-at-a-1-point-25t-valuation-what-it-means-for-the-ipo.html',
'coreweave_semafor_retry':'https://www.semafor.com/article/11/13/2026/coreweave-tunes-out-nvidia-noise-looks-to-raise-4b',
'coreweave_fool':'https://www.fool.com/coverage/stock-market-today/2026/11/13/stock-market-today-nov-13-coreweave-falls-over-6-on-ai-cloud-selling-and-reported-4-billion-loan-talks/',
'openai_q3_search':'https://news.google.com/rss/search?q=OpenAI+%22quarterly%22+%22revenue%22+when%3A2d&hl=en-US&gl=US&ceid=US:en',
'coreweave_credit_search':'https://news.google.com/rss/search?q=CoreWeave+%22Bonds%22+%22cooling%22+when%3A2d&hl=en-US&gl=US&ceid=US:en'
}

def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,final_url=r.url,bytes=len(b));(p/(k+('.xml' if k.startswith('bing_') else '.html'))).write_bytes(b)
  s=b.decode(errors='replace');d['canonical']=re.findall(r'<link[^>]*rel=["\']canonical["\'][^>]*>',s);d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);d['links']=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',s) if any(t in x for t in ['cnbc.com','bloomberg.com','ft.com','theinformation.com'])];s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:27000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'originals_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,ensure_ascii=False,indent=2))
