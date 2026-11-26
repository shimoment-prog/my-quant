import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/bigtech')
us={'msft_investing_link': 'https://news.google.com/rss/articles/CBMiyAFBVV95cUxOQUV6VXo0d0NQLWVUT3huT3ZSRmZWeUp0T3JqSUEwdWd5WXhSUEgxRm5wVXMyUU9kTm9ON3AxaWNZV1BfLUw2RmdtWXdZa1JCX1BuOWlnOW12UURkajlnb0tsY1U4azY3WWVSZUE2RjVHczlCOWR4SnhhMER2ZHU2TXN5YnBEcnBCMGtPemwzRGFQbTVGU3RnM0EzM3hkR3hOQzd1eUZ0ZERXZGpNdWFsZE9nbzVXSzRaYWRDM0V6d0owUF9aU3kwZw?oc=5', 'msft_tradingview_link': 'https://news.google.com/rss/articles/CBMi5gFBVV95cUxOY2paajB2djZud0RBRkx1MEdFdDZLZS1rX2JPUXlMVDF3T0VILTNjSVZYRFFQTFU1S1dJNUhTMzRfcUZ0ZmVxQnk1MFhwbE9pU3hSUlNiVVNfZjM0cVdqcThtaDZkXzctSjVfUFU1SFUydEs3U1diYmNLN1NSUThUNks3aUZ5elhoYk9HOS1YeUZoLTZKYTlYczlURk1PZTBnVTBFM2Y0WEkwcWxYRTVGeXJWS0pQb2xnVkxxdjQwQldFVEUzbWFfQzhZX0hwVmxwVk9mTkhFZGFlZHN0TzUtMEdsd0pYQQ?oc=5', 'msft_neowin_link': 'https://news.google.com/rss/articles/CBMivAFBVV95cUxPSElORHVLWWtmdmJDZkQ2UkJ1dHpFckdqWV82QkIyd3RwWmdyTnVjNThMZXpnOW1iOGJQUkstVEtXdGQ1Sm8yOUtVdW1sVktmaGROem55V1lmSXZGNmlmWm40OTVsaGxORFpEd3F2RXlSUGFSWHZvTzVtR1otTWgtOHA3bklCZHFSUTJFbHdPemRfenR4OGhDZ3FURFUwZmN1RlRmTVlQUlFUdjV3ZWNxU2poWVVXbjFGUGt0Tg?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'syndication_links_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
