import json,re,datetime,concurrent.futures,urllib.request,urllib.parse,html,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__file__).parent
jobs={
'ciena_8k':'https://www.sec.gov/Archives/edgar/data/936395/000162828026074023/cien-20261116.htm',
'blackstone_index':'https://www.blackstone.com/news/press/',
'blackstone_release':'https://www.blackstone.com/news/press/blackstone-digital-infrastructure-trust-announces-5-billion-acquisition-of-stabilized-data-center-portfolio/',
'westbank_news':'https://westbankcorp.com/news',
}
j=json.loads((p/'amd_submissions.json').read_text())['filings']['recent']
for i,f in enumerate(j['form']):
 if f=='8-K/A' and j['acceptanceDateTime'][i]>'2026-11-16T00:32:08.760704':jobs['amd_8ka']='https://www.sec.gov/Archives/edgar/data/2488/'+j['accessionNumber'][i].replace('-','')+'/'+j['primaryDocument'][i]
queries={'telus_search':'"TELUS" "Westbank" "November" "2026" when:3d','muskie_search':'"Muskie" "Kentucky Power" when:3d'}
jobs.update({n:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for n,q in queries.items()})
def f(e):
 n,u=e;r={'name':n,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  h=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Public research research@example.com' if 'sec.gov' in u else 'Mozilla/5.0'}),timeout=18);d=h.read();r['final_url']=h.url;(p/(n+'.html')).write_bytes(d);s=d.decode('utf8','replace');t=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.I|re.S)));t=re.sub(r'\s+',' ',t);(p/(n+'.txt')).write_text(t);r.update(ok=True,chars=len(t))
  if n in queries:
   z=ET.fromstring(d);r['items']=[{k:i.findtext(k) for k in ['title','link','pubDate','source']} for i in z.findall('./channel/item')][:15]
  if n in ('amd_8ka','ciena_8k','blackstone_release'):r['text']=t[:25000]
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:r=list(ex.map(f,jobs.items()))
(p/'followup_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
