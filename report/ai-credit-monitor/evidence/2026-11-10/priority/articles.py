import urllib.request,json,datetime,pathlib,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-10/priority')
urls={'coreweave_cnbc':'https://www.cnbc.com/2026/11/09/coreweave-debt-credit-risk-neoclouds.html','openai_aws':'https://openai.com/index/chatgpt-enterprise-aws-marketplace','coreweave_form4':'https://www.sec.gov/Archives/edgar/data/1769628/000176962826000457/form4.xml','coreweave_form144':'https://www.sec.gov/Archives/edgar/data/1769628/000195004726010854/primary_doc.xml'}
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Research analyst contact analyst@example.com' if 'sec.gov' in u else 'Mozilla/5.0','Accept':'text/html,application/xml,*/*'}),timeout=18);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+('.xml' if 'form' in k else '.html'))).write_bytes(b)
  s=b.decode(errors='replace');d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(lambda kv:get(*kv),urls.items()));(p/'articles_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
