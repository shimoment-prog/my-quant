import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/bigtech')
us={
'reuters_msft':'https://www.reuters.com/world/china/microsoft-presses-trump-scuttle-expected-ban-chinese-data-center-technology-2026-11-10/',
'reuters_anthropic':'https://www.reuters.com/business/anthropic-eyes-14-trillion-ipo-valuation-test-wall-streets-ai-fervor-2026-11-10/',
'anthropic_news':'https://www.anthropic.com/news',
'sec_anthropic':'https://efts.sec.gov/LATEST/search-index?q=%22Anthropic%22&dateRange=custom&startdt=2026-11-09&enddt=2026-11-11&forms=S-1%2CS-1%2FA',
'msft_rss_link':'https://news.google.com/rss/articles/CBMizwFBVV95cUxPYVBfNG04eWF0OFp6WHJFRFh3YjdHTHlhdU9xTkZiU3h1Qk9OdXpmM0FaZS1vcXJkdFdHRmE2a0ROLWRWYzNWUXhtcGpmVjREYjBJUC1nYzVSZkxPaHA5dVNNSlhpZzVlX2FOVElnZWNPZ0VuVS1sWEQ5cVNQYXYtT3MtUGppSTIzQ25YX0Q1UnFDbzZxc1RITGRRT1ZNeUFKQTZxWlJxc0E5Z0JjdVVEaXIxbmlqdGRZYzVsLWtRWTBuUlJsb3BTZVAwN1RYWlk?oc=5', 'anthropic_rss_link':'https://news.google.com/rss/articles/CBMisAFBVV95cUxNaUtnS210c1pKNVpEZXJ1V1JpdUdyZ0h5OGh2SzVCXzJaVGRwaDZnb0NQZUxFS0ZFWmxwbU53ZlJtdlBkOWplZHdaNkloU0xwV3hvdlpjNnh0R1FISXdMOExfc09JckJqTWxjSWlZSjZpN0RWR1kyRUF6YUlXN0dqSm5XQU5TUmFmbWpFbGlzT3FZRllaMGU4cld0cDlsaFVYY0IzV2ZNYmwxYW0yd1FDaw?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'direct_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
