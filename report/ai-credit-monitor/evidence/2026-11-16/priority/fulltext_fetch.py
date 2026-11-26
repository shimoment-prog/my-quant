import urllib.request,json,datetime,pathlib,concurrent.futures,re,html
p=pathlib.Path(__file__).parent
urls={
    'qts_investinglive':'https://investinglive.com/stocks/weekend-blackstone-s-qts-cuts-ai-data-center-debt-sale-60-as-investors-push-back-on-pricing/',
    'coreweave_dealroom':'https://app.dealroom.co/news/note/coreweave-lands-8-5b-debt-deal-cementing-a-trillion-dollar-ai-lending-playbook',
}
def get(k,u):
    d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,*/*'}),timeout=20)
        b=r.read();d.update(status=r.status,final_url=r.url,bytes=len(b));(p/(k+'.html')).write_bytes(b)
        s=b.decode(errors='replace')
        d['canonical']=re.findall(r'<link[^>]*rel=["\']canonical["\'][^>]*>',s)
        d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S)
        d['links']=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',s) if any(t in x for t in ['cnbc.com','bloomberg.com','ft.com','reuters.com','coreweave.com'])]
        s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I)
        s=html.unescape(re.sub(r'<[^>]+>',' ',s))
        s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip())
        (p/(k+'.txt')).write_text(s);d['text']=s[:35000]
    except Exception as e:d['error']=str(e)
    return d
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda kv:get(*kv),urls.items()))
(p/'fulltext_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
