import pathlib,urllib.request,urllib.parse,re,html,datetime,json,concurrent.futures,xml.etree.ElementTree as E
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-12/bigtech')
qs={'news_msft_oracle':'Microsoft Chinese optical transceiver ban after:2026-11-10','news_buyer_cuts':'Alphabet Meta Amazon Microsoft capital spending cut financing after:2026-11-10','news_broadcom':'Broadcom AI financing guarantee order after:2026-11-10','news_asia':'Alphabet Hong Kong Singapore bonds after:2026-11-10', 'news_meta_power':'Meta Louisiana power lawsuit after:2026-11-10','news_anthropic':'Anthropic IPO placement priced after:2026-11-10'}
us={n:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for n,q in qs.items()}
us.update({'google_rss':'https://blog.google/rss/','msft_blog_rss':'https://blogs.microsoft.com/feed/','meta_ir':'https://investor.atmeta.com/investor-news/default.aspx','amazon_ir':'https://ir.aboutamazon.com/news-release/news-release-details/default.aspx','broadcom_ir':'https://investors.broadcom.com/news-events/press-releases'})
def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  if '_rss' in n or n.startswith('news'):
   try:
    for x in E.fromstring(raw).findall('./channel/item')[:30]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
   except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'news_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
