import urllib.request,urllib.parse,json,pathlib,concurrent.futures,re,html
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-07/priority')
u={'cnbc_sitemap':'https://www.cnbc.com/sitemap_news.xml','cnbc_sitemap_alt':'https://www.cnbc.com/sitemap.xml','google_search':'https://www.google.com/search?q='+urllib.parse.quote('site:cnbc.com/2026/11/06/ "CoreWeave" "credit"'),'bing_search':'https://www.bing.com/search?q='+urllib.parse.quote('site:cnbc.com/2026/11/06/ "CoreWeave" "credit"'),'cnbc_rss':'https://www.cnbc.com/id/100003114/device/rss/rss.html','quartz_search':'https://qz.com/search?q=CoreWeave'}
def get(k,v):
 d={'name':k,'url':v}
 try:
  r=urllib.request.urlopen(urllib.request.Request(v,headers={'User-Agent':'Mozilla/5.0'}),timeout=18);s=r.read().decode(errors='replace');(p/(k+'.txt')).write_text(s);d.update(status=r.status,bytes=len(s));d['matches']=list(dict.fromkeys(re.findall(r'https?://[^\s<>"\x27\\]+',html.unescape(s))))[:120] if 'sitemap' in k else list(dict.fromkeys(x for x in re.findall(r'https?://[^\s<>"\x27\\]+',html.unescape(s)) if any(a in x.lower() for a in ['coreweave','data-center-loans','ifr','credit-card'])))[:30]
 except Exception as e:d['error']=str(e)
 return d
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),u.items()));(p/'urls_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
