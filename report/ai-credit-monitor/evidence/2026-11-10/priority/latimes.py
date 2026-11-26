import urllib.request,json,datetime,pathlib,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-10/priority')
u='https://www.latimes.com/business/story/2026-11-09/openai-closes-latest-funding-round-at-1-25-trillion-valuation'
d={'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
 r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=12);b=r.read();d.update(status=r.status,bytes=len(b));(p/'latimes.html').write_bytes(b)
 s=b.decode(errors='replace');d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/'latimes.txt').write_text(s);d['text']=s
except Exception as e:d['error']=str(e)
(p/'latimes_manifest.json').write_text(json.dumps(d,indent=2));print(json.dumps(d,indent=2))
