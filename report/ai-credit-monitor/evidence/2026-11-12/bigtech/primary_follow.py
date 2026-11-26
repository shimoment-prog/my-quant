import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-12/bigtech')
us={'anthropic_news': 'https://www.anthropic.com/news', 'anthropic_roadshow': 'https://www.anthropic.com/news/roadshow-launch', 'news_asia_link': 'https://news.google.com/rss/articles/CBMimgFBVV95cUxONGJpYVZRX0pQWGxTc1dQcmxhSktPVlF4QWhld3lBdnJaRkIzREZUZUgweU9YbjFXaGxFY1Jrc29paG50TC1IQUljSnBMaHBGQzN0Z1NncFgtckU2QXhsZGZLbkZrYWQycU4xWTZ1VGhPcDI1SDdQWGd0OWZqdHVmWHhxU1BDSTlnN1VyQU1taUR2Qk5WQUhBTXln?oc=5', 'news_anthropic_link': 'https://news.google.com/rss/articles/CBMirgFBVV95cUxOUTgtOV9zN3Ywb2UycWxaSlNwOGltSV91cjMtRWdlNnJibWhnTVgtQkZkd0ZYU0NweVB5MEhaMkd6ZVNpUXlra3JiQ2ltcU4xUUUta0pPV2dqb19uWWpLZWVkanNqTnlsVEo2YmdFeGw2M2dNcGtGVHdGb1hBMTN4MFRteXhkbUctZWIxSURUQjcxczZxbmdtbGQ0d3ZLWWJCcjFQQVpwb1pjNHNzWlE?oc=5', 'news_msft_oracle_link': 'https://news.google.com/rss/articles/CBMi5wFBVV95cUxOd2w1M2ZRVjBHSFp5Qnh5R29XZ1VpUU5USVNCUUVTWEJPNGRIcGF5d244VnJPbHM3akJBQ0JnNkFYY0pRV2ZvdWF5dUdlNWs0aFRCalloV1NOa2pra3IyMFR3ckg5QUZHdW96RkZmdjUzVFh5eVh4djhnOW9hMzBhRlNuWnBrbS1FQTJXSFczdDktTGktMTZpQUJhdHlyX05xNF9vMWQ1XzBPQlVkaVZROWdjOWRqeUdjN21VZTRQX0tma3pEcm1sSm9meGZtNEFzZi1odHEtU3gwQkM5OWU2NHlUTGZSc0E?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'primary_follow_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
