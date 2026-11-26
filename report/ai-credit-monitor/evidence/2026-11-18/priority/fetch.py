import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET,re,html
p=pathlib.Path('report/ai-credit-monitor/evidence/2026-11-18/priority')
urls={'coreweave_submissions':'https://data.sec.gov/submissions/CIK0001769628.json','coreweave_ir':'https://investors.coreweave.com/news-and-events/news-releases','nebius_submissions':'https://data.sec.gov/submissions/CIK0001513845.json','nebius_news':'https://nebius.com/newsroom','openai_news':'https://openai.com/news/rss.xml'}
for k,q in {'news_priority':'(Oracle OR CoreWeave) (debt OR financing OR CDS OR default OR guidance) when:1d','news_openai':'OpenAI (funding OR fundraising OR "15 billion") when:1d','news_coreweave_funding':'CoreWeave (loan OR financing OR bonds OR default) when:1d','news_ing':'ING CoreWeave (sale OR loan OR BWIC) when:7d','news_hsbc':'HSBC data center loan Oracle discount when:2d','news_nebius':'Nebius (financing OR delay OR loan OR capex OR cancellation) when:1d','news_blackstone':'Blackstone Amazon data center 5 billion when:2d','news_qts':'QTS (debt OR placement OR financing OR Thunder) when:1d'}.items():urls[k]='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Research analyst contact analyst@example.com' if 'sec.gov' in u else 'Mozilla/5.0','Accept':'application/json,text/html,*/*'}),timeout=20);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+('.json' if 'submissions' in k else '.xml' if k.startswith('news_') else '.html'))).write_bytes(b)
  if 'submissions' in k:
   j=json.loads(b)['filings']['recent'];rows=[{x:j[x][i] for x in j} for i in range(len(j['form']))];d['new_filings']=[x for x in rows if x['acceptanceDateTime']>'2026-11-17T02:22:43.455452Z'];d['latest_operating_filings']=[x for x in rows if x['form'] in ['10-Q','10-K','8-K']][:2]
  if k.startswith('news_'):d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link']} for el in ET.fromstring(b).findall('.//item')][:22]
  if k in ['microsoft_oracle_cnbc','openai_techcrunch']:
   s=b.decode(errors='replace');d['jsonld']=re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',s,flags=re.S);s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',s,flags=re.S|re.I);s=html.unescape(re.sub(r'<[^>]+>',' ',s));s='\n'.join(' '.join(x.split()) for x in s.splitlines() if x.strip());(p/(k+'.txt')).write_text(s);d['text']=s[:13000]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
