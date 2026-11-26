import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-13/bigtech')
us={'asia_reuters':'https://www.reuters.com/world/asia-pacific/alphabet-sets-initial-price-guidance-hong-kong-singapore-bond-sales-term-sheet-2026-11-12/','asia_cod':'https://www.centraloregondaily.com/news/consumer/alphabets-debut-hong-kong-singapore-bond-sales-draw-over-7-billion-in-orders/article_892f1d37-8820-5d81-9179-9d476efa458c.html','asia_quartz':'https://qz.com/alphabet-hong-kong-singapore-dollar-bonds-debut-111226','asia_standard':'https://www.thestandard.com.hk/finance/article/348286/Alphabets-debut-Hong-Kong-Singapore-bond-sales-draw-about-US5-billion-in-early-orders'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'asia_articles_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
