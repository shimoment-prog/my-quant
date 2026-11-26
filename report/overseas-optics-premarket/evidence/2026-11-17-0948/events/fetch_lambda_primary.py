exec(open('/private/tmp/optics-nov17-events/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
url='https://lambda.com/blog/worlds-first-large-scale-deployment-of-nvidia-photonics-switches-with-cpo'
m=get(('lambda_deployment',url));(R/'lambda_primary_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));print(m)
if m['ok']:
 from html.parser import HTMLParser
 class P(HTMLParser):
  def __init__(self):super().__init__();self.skip=0;self.txt=[]
  def handle_starttag(self,t,a):
   if t in ['script','style']:self.skip+=1
  def handle_endtag(self,t):
   if t in ['script','style']:self.skip=max(0,self.skip-1)
  def handle_data(self,d):
   if not self.skip and d.strip():self.txt.append(d.strip())
 p=P();p.feed((R/'lambda_deployment.txt').read_text());s='\n'.join(p.txt);(R/'lambda_deployment_clean.txt').write_text(s);print(s[:23000])
