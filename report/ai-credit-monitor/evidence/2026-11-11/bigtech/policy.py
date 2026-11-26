import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/bigtech')
us={'msft_reuters_syndicated':'https://www.tradingview.com/news/reuters.com,2026:newsml_L1N44S0ZZ:0-microsoft-presses-trump-to-scuttle-expected-ban-on-chinese-data-center-technology/','msft_neowin':'https://www.neowin.net/news/microsoft-reportedly-wants-trump-to-keep-chinese-ai-data-center-components-coming-to-the-us/','msft_investing_correct':'https://www.investing.com/news/stock-market-news/microsoft-pushes-trump-to-halt-chinese-data-center-component-ban-reuters-5014871'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'policy_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
