import urllib.request,urllib.parse,concurrent.futures,json,re,html,datetime
from pathlib import Path
p=Path(__file__).parent
jobs={
 'telus_bing':'https://www.bing.com/search?q='+urllib.parse.quote('"Telus" "Westbank" "2026" "November"'),
 'tokenpost_search':'https://www.tokenpost.com/search?keyword=TELUS',
 'financialpost_search':'https://financialpost.com/?s='+urllib.parse.quote('Telus AI Vancouver'),
 'maple_search':'https://www.mapleridgenews.com/search?search=Telus',
 'telus_news':'https://www.telus.com/en/about/news-and-events/media-releases',
 'bxdc_home':'https://www.bxdc.com/',
 'blackstone_commercialsearch':'https://www.commercialsearch.com/news/blackstone-to-pay-5b-for-data-center-portfolio/'
}
def f(e):
 n,u=e;r={'name':n,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as h:d=h.read();r['final_url']=h.url
  (p/(n+'.html')).write_bytes(d);s=d.decode('utf8','replace');t=html.unescape(re.sub('<[^>]+>',' ',re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.I|re.S)));t=re.sub(r'\s+',' ',t);(p/(n+'.txt')).write_text(t);r.update(ok=True,chars=len(t));r['text']=t[:18000]
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:r=list(ex.map(f,jobs.items()))
(p/'search_originals_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
