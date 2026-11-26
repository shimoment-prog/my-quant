import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-14/priority')
urls={
'qts_google':'https://www.google.com/search?q=%22QTS%22+%22private+debt%22+%22300%22&hl=en',
'qts_bt_alt':'https://www.businesstimes.com.sg/companies-markets/blackstones-qts-is-cutting-ai-debt-sale-by-more-than-half',
'qts_tu_search':'https://tradersunion.com/search/?q=QTS',
'qts_marketscreener_search':'https://www.marketscreener.com/search/?q=Blackstone-Backed%20QTS',
'qts_yahoo':'https://finance.yahoo.com/news/blackstone-qts-cutting-ai-debt-222156445.html'
}

def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,final_url=r.url,bytes=len(b));(p/(k+('.xml' if k.startswith('bing_') else '.html'))).write_bytes(b)
  s=b.decode(errors='replace');d['canonical']=re.findall(r'<link[^>]*rel=["\']canonical["\'][^>]*>',s);d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);d['links']=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',s) if any(t in x for t in ['cnbc.com','bloomberg.com','ft.com','theinformation.com'])];s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:27000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'qts_more_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,ensure_ascii=False,indent=2))
