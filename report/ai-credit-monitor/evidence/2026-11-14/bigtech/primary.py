import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-14/bigtech')
us={'asia_straits': 'https://www.straitstimes.com/business/companies-markets/alphabets-debut-hong-kong-singapore-bond-sales-draw-about-us5b-in-early-orders', 'asia_standard': 'https://www.thestandard.com.hk/finance/article/348350/Alphabet-raises-US38-billion-in-first-Hong-Kong-Singapore-dollar-bonds', 'asia_channel': 'https://www.channelinsider.com/infrastructure/news-alphabet-3-8-billion-asian-bonds-ai-infrastructure-apac/', 'asia_aol': 'https://www.aol.com/articles/alphabet-sets-initial-price-guidance-025732000.html', 'anthropic_inkl': 'https://www.inkl.com/news/anthropic-ipo-prices-shares-at-78-ahead-of-november-19-debut-can-ant-stock-become-the-next-big-ai-investment-amid-nvidia-stock-crash-and-jensen-huang-fallout', 'broadcom_redburn': 'https://uk.investing.com/news/stock-market-news/rothschild-downgrades-broadcom-stock-rating-on-ai-financing-concerns-93CH-4979931', 'anthropic_roadshow': 'https://www.anthropic.com/news/roadshow-launch', 'asia_reuters': 'https://www.reuters.com/world/asia-pacific/alphabet-sets-initial-price-guidance-hong-kong-singapore-bond-sales-term-sheet-2026-11-12/'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'primary_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
