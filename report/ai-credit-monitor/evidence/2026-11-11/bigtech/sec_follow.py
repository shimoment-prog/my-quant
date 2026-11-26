import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/bigtech')
us={
'reuters_msft_tech':'https://www.reuters.com/technology/microsoft-presses-trump-scuttle-expected-ban-chinese-data-center-technology-2026-11-10/',
'reuters_anthropic_tech':'https://www.reuters.com/technology/anthropic-eyes-14-trillion-ipo-valuation-test-wall-streets-ai-fervor-2026-11-10/',
'sec_company_browse':'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=Anthropic&owner=exclude&count=40',
'sec_company_search':'https://efts.sec.gov/LATEST/search-index?q=Anthropic&dateRange=custom&startdt=2026-11-09&enddt=2026-11-11',
'reuters_msft_print':'https://www.reuters.com/technology/artificial-intelligence/microsoft-presses-trump-scuttle-expected-ban-chinese-data-center-technology-2026-11-10/'
}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'sec_follow_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
