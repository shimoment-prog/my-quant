import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-12/priority')
urls={'oracle_submissions':'https://data.sec.gov/submissions/CIK0001341439.json','coreweave_submissions':'https://data.sec.gov/submissions/CIK0001769628.json','oracle_ir':'https://investor.oracle.com/investor-news/default.aspx','coreweave_ir':'https://investors.coreweave.com/news-and-events/news-releases','microsoft_oracle_cnbc':'https://www.cnbc.com/2026/11/06/microsoft-moves-to-consolidate-its-relationships-with-neoclouds-in-ai.html','openai_techcrunch':'https://techcrunch.com/2026/11/06/openai-reportedly-raises-an-additional-11-billion-at-a-1-25-trillion-valuation/'}
for k,q in {'news_priority':'(Oracle OR CoreWeave) (debt OR financing OR CDS OR default OR guidance) when:1d','news_openai':'OpenAI (funding OR fundraising OR "Microsoft Oracle") (closed OR confirmed OR billion) when:1d'}.items():urls[k]='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Research analyst contact analyst@example.com' if 'sec.gov' in u else 'Mozilla/5.0','Accept':'application/json,text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+('.json' if 'submissions' in k else '.xml' if k.startswith('news_') else '.html'))).write_bytes(b)
  if 'submissions' in k:
   j=json.loads(b)['filings']['recent'];rows=[{x:j[x][i] for x in j} for i in range(len(j['form']))];d['new_filings']=[x for x in rows if x['acceptanceDateTime']>'2026-11-11T01:14:46Z'];d['latest_operating_filings']=[x for x in rows if x['form'] in ['10-Q','10-K','8-K']][:2]
  if k.startswith('news_'):d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link']} for el in ET.fromstring(b).findall('.//item')][:22]
  if k in ['microsoft_oracle_cnbc','openai_techcrunch']:
   s=b.decode(errors='replace');d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:13000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
