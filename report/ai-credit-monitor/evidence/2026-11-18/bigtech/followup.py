import pathlib,urllib.request,urllib.parse,re,html,datetime,json,concurrent.futures,xml.etree.ElementTree as E
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-18/bigtech')
us={'anthropic_s1a_retry': 'https://www.sec.gov/Archives/edgar/data/2130357/000162828026074338/anthropicpbc-sx1ax3.htm', 'anthropic_8a_retry': 'https://www.sec.gov/Archives/edgar/data/2130357/000162828026074342/anthropic-8xa12b.htm', 'anthropic_cnbc_price_link': 'https://news.google.com/rss/articles/CBMiZ0FVX3lxTE9PTUZvUHlERUszRUFVdjJSRW84TnpvQ25Ndkk1Ty1kblozSVh6VUVyTUZ1ZjBCdlFYa0s3cHhNYUM5R3ZrVEdZeVdpa2IzT0lzbWkwUzVUTjdaZXdEVTdLa3h3ZG14ODDSAWxBVV95cUxOWmU0cWFuWmtwUFZYZVRWTnd0NXVVRnBHNGh2RTlmSGRacHhXb1ZnOTQ3Si1sMUU2ZkE5MWlTRU50NnY2V2NpNnFXdEJxeW0zaHRpZk1wajRoWVp2b25IUXlDbDF5azFxX2JZMjQ?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research monitor contact research@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  if '_rss' in n or n.startswith('news'):
   try:
    for x in E.fromstring(raw).findall('./channel/item')[:30]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
   except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'followup_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
