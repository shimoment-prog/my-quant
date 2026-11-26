import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-16/bigtech')
us={'google_power_link': 'https://news.google.com/rss/articles/CBMivwFBVV95cUxNM2Ztc2QzQlJuTzMwWS02Tk4xdHlqZGF3ZDVXd2JNaW5pY2FZaHRBczdtV0cxenNuMmcwcmhVWE9GMGhQT1JGWGROa1dpVnFoU19oejJUekZjdGlvYWh5eXBUQWpvUEJPRzZSaXR1R3BjSWphTzlJMDFkdU1oS0JtdWNzbWlTRUxyNUdJZUFfaVpGcWNLRjNUZjJfa2otb0dfVVZJVXZmNFlSWGFkQnFyYnQ3RG43dmJxQU1fc19CZw?oc=5', 'google_construction_link': 'https://news.google.com/rss/articles/CBMiuAFBVV95cUxOQm5IYWFGbjU4emhEMkpKeGROakhVVGtCUU1xTEFzeTBqeUJTSnpBT291MTUtYjBFRmM4MGZSejZnblpnLWttcEZ5Sms0c1JTbHF5ODlxckEyYU9lSFI0X05QUjFPWHNreGFLSG5jeGlEcTFsLWVFaXNOLWdRazNnSElqRktCdFNuTmhLeXI1dXR1SWlmY252UVdFWDg1aGxuWkM0bzNuT3ZHQklxU3g5S2xDbFpzWU1i?oc=5', 'meta_recap_link': 'https://news.google.com/rss/articles/CBMiywFBVV95cUxNUVBQQnREaHBhVnByYVlfMGZjWVFzOG1TMnFiT0V4cEpObHFId0s0UHdLdV9UMzVVUnowdG5XcU90cUFLdFBTN08xZUtMcHZNcDJvZjllMVFfemdxQlN3eGlBRVZ0eFZieS1Ka3VVTkhYY3o4ZndEM2JvQjZZYjEwM2VHSGRMUUFqTHZKQ045SjJ1cGNNdE9oZHlReFZQajl0MnkyMUVGOF9JVWN4SzdKMVdjQldabVpFLXJmQktwb1I0Z1dKUC16VUNqcw?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'project_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
