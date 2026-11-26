import urllib.request,datetime,json,re,concurrent.futures
from pathlib import Path
from html.parser import HTMLParser
b=Path(__file__).resolve().parent
urls={"apollo_new_notes_ir":"https://ir.apollo.com/news-events/press-releases/detail/659/apollo-prices-offering-of-fixed-rate-resettable-junior","apollo_new_notes_fwp":"https://www.sec.gov/Archives/edgar/data/1858681/000095014226002981/eh260853424_fwp.htm","lite_425_20261109":"https://www.sec.gov/Archives/edgar/data/1633978/000119312526453776/d180680d425.htm"}
class P(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.out=[]
 def handle_starttag(self,t,a):
  if t in ("script","style"):self.skip+=1
 def handle_endtag(self,t):
  if t in ("script","style"):self.skip=max(0,self.skip-1)
 def handle_data(self,d):
  if not self.skip and d.strip():self.out.append(d.strip())
def f(z):
 k,u=z;r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Public researcher research@example.com"}),timeout=15) as h:d=h.read()
  (b/(k+".html")).write_bytes(d);p=P();p.feed(d.decode("utf-8","replace"));s=" ".join(p.out);(b/(k+".txt")).write_text(s);r.update(ok=True,text=s)
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=list(ex.map(f,urls.items()))
(b/"docs_manifest.json").write_text(json.dumps([{k:v for k,v in r.items() if k!="text"} for r in out],indent=2))
for r in out:print(json.dumps(r))
