import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-14/priority')
urls={
'coreweave_mlq':'https://mlq.ai/news/coreweave-seeks-a-4-billion-loan-backed-by-its-meta-contracts-semafor-reports/',
'coreweave_semafor_withoutwww':'https://semafor.com/article/11/13/2026/coreweave-tunes-out-nvidia-noise-looks-to-raise-4b',
'openai_tnw_search':'https://thenextweb.com/?s=OpenAI+quarterly+revenue',
'openai_tnw':'https://thenextweb.com/news/openai-quarterly-revenue-10bn-losses',
'coreweave_google_source':'https://news.google.com/rss/articles/CBMimAFBVV95cUxNanJCYjB6NHNwNTZ4bGI1R0dOQXRNWVdkRVFzeDc3UlUtblhwMmtVSEFvcVR4N0R2ZXQ4VHRISW1yaFRiOFVHRjZHY2ctWDZXNFBJVEZmVHlaZWhtY2g2U0xCemplQ3FMaWVEcVdud05rcS1RdzBXYmF1elZGTGRNaGcxZUdFNGNBR3RUeFJIYmlhSHo2VWpncw?oc=5'
}

def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,final_url=r.url,bytes=len(b));(p/(k+('.xml' if k.startswith('bing_') else '.html'))).write_bytes(b)
  s=b.decode(errors='replace');d['canonical']=re.findall(r'<link[^>]*rel=["\']canonical["\'][^>]*>',s);d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);d['links']=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',s) if any(t in x for t in ['cnbc.com','bloomberg.com','ft.com','theinformation.com'])];s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:27000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'follow_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,ensure_ascii=False,indent=2))
