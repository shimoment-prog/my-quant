exec(open('/private/tmp/optics-nov17-events/fetch_primary.py').read().split('urls={')[0])
urls={'nvda_lambda_photonics':'https://blogs.nvidia.com/blog/lambda-photonics/','nvda_supply_chain':'https://blogs.nvidia.com/blog/ai-infrastructure-supply-chain/'}
man=[get(x) for x in urls.items()]
(R/'lambda_manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
from html.parser import HTMLParser
class P(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.txt=[]
 def handle_starttag(self,t,a):
  if t in ['script','style']:self.skip+=1
 def handle_endtag(self,t):
  if t in ['script','style']:self.skip=max(0,self.skip-1)
 def handle_data(self,d):
  if not self.skip and d.strip():self.txt.append(d.strip())
for m in man:
 print(m)
 if m['ok']:
  p=P();p.feed((R/(m['name']+'.txt')).read_text());s='\n'.join(p.txt);(R/(m['name']+'_clean.txt')).write_text(s);print(s[:16000])
