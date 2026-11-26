import urllib.request,urllib.parse,json,datetime,pathlib,concurrent.futures,xml.etree.ElementTree as ET
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-07/priority')
urls={'oracle_submissions':'https://data.sec.gov/submissions/CIK0001341439.json','coreweave_submissions':'https://data.sec.gov/submissions/CIK0001769628.json','oracle_ir':'https://investor.oracle.com/investor-news/default.aspx','coreweave_ir':'https://investors.coreweave.com/news-and-events/news-releases','oracle_newsroom':'https://www.oracle.com/news/','coreweave_newsroom':'https://www.coreweave.com/news'}
qs={'news_oracle':'Oracle debt financing CDS capex guidance cancellation November 6 2026 when:1d','news_coreweave':'CoreWeave debt CDS financing guidance November 6 2026 when:1d','news_500m':'"data center loans" "$500" when:2d','news_76':'CoreWeave bonds "76" when:2d'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for k,q in qs.items()})
def get(k,u):
 d={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Research analyst contact analyst@example.com' if 'sec.gov' in u else 'Mozilla/5.0','Accept':'application/json,text/html,*/*'}),timeout=25);b=r.read();d.update(status=r.status,bytes=len(b));(p/(k+('.json' if 'submissions' in k else '.xml' if k.startswith('news_') else '.html'))).write_bytes(b)
  if 'submissions' in k:
   j=json.loads(b)['filings']['recent']; rows=[{x:j[x][i] for x in j} for i in range(len(j['form']))]; d['new_filings']=[x for x in rows if x['acceptanceDateTime']>'2026-11-06T00:39:28Z']; d['latest_operating_filings']=[x for x in rows if x['form'] in ['10-Q','10-K','8-K']][:3]
  if k.startswith('news_'):d['items']=[{a:el.findtext(a) for a in ['title','pubDate','link']} for el in ET.fromstring(b).findall('.//item')][:22]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
