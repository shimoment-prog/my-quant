import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-13/bigtech')
us={'anthropic_news': 'https://www.anthropic.com/news', 'anthropic_roadshow': 'https://www.anthropic.com/news/roadshow-launch', 'meta_8A12B_3': 'https://www.sec.gov/Archives/edgar/data/1326801/000119312526458695/d193866d8a12b.htm', 'meta_8K_4': 'https://www.sec.gov/Archives/edgar/data/1326801/000119312526458525/d177728d8k.htm', 'anthropic_FWP_0': 'https://www.sec.gov/Archives/edgar/data/2130357/000162828026073045/anthropicpbc-fwpjapanamend.htm', 'anthropic_FWP_1': 'https://www.sec.gov/Archives/edgar/data/2130357/000162828026073040/anthropicpbc-fwpxeeaprospea.htm'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'primary_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
