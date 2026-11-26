import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-16/bigtech')
us={'anthropic_yahoo_trade_link': 'https://news.google.com/rss/articles/CBMilgFBVV95cUxNU3hRdTVPNVJTa2haOXlaVFRxWkpkRDNhT2JMamV1R2IwS0owSC1YWHdXREdaLU5LUWhrclQxRnBHUGdXeUhSMDVUWjF2ejA5UFZ4V2xYdDNwMW9qNDBYa1BlaTYzMWZBTlozQjZ1eXEyUzM2MzVfS3BCTjgwb3lLaTdUQUdJeVhyQ2dvUlZNNFlsRFNDMEE?oc=5', 'anthropic_yahoo_week_link': 'https://news.google.com/rss/articles/CBMizwFBVV95cUxPRGowX3ljRUhFOUtMR2diRUJHR2xTalpGZExTNFRKTExUQTQ2cUtNQXZfWEVRM3BMYldsOEh2czRtSmJZVExCakN0Q2VaWVRWWmFSYjRsRFBqNzRucXh1c2pIcW84aDUzdkhjY3pyZFFkVjRSN2gzU0dNM1NEWXI2WHIxdXl0OTB4OVM3QVVsSXg5V2NUQVVLVmZJWURyaWhXOUxyTWE3cm1qVXRQTFktZWQ0Y3hmaWlaenFrTi1jc3ZPSTFlWUVEbXRaYUVQOU0?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'discovery_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
