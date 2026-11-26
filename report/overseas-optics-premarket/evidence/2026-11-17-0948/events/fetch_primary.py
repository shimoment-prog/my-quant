exec(open('/private/tmp/optics-nov17-events/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
urls={
'cien_8k':'https://www.sec.gov/Archives/edgar/data/936395/000162828026074023/cien-20261116.htm',
'mrvl_penguin':'https://investor.marvell.com/news-events/press-releases/detail/1044/marvell-and-penguin-solutions-collaborate-to-address-data-center-ai-memory-and-accelerate-inference-at-scale',
'nvda_rubin_hpc':'https://blogs.nvidia.com/blog/rubin-hpc/',
'nvda_vera_cpu':'https://nvidianews.nvidia.com/news/nvidia-expands-vera-cpu-platform-to-accelerate-scientific-discovery',
'nvda_nemotron':'https://nvidianews.nvidia.com/news/nvidia-introduces-nemotron-for-science-to-accelerate-discoveries-with-agents',
'cohr_press':'https://www.coherent.com/news/press-releases',
'blackstone_news':'https://www.blackstone.com/news/press/',
'nvda_13f':'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000084/xslForm13F_X02/primary_doc.xml'
}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:man=list(ex.map(get,urls.items()))
(R/'primary_manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
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
  p=P();p.feed((R/(m['name']+'.txt')).read_text());s='\n'.join(p.txt);(R/(m['name']+'_clean.txt')).write_text(s)
  if m['name'] in ['cien_8k','mrvl_penguin','nvda_rubin_hpc','nvda_vera_cpu','nvda_13f']:print('TEXT',m['name'],s[:17000])
