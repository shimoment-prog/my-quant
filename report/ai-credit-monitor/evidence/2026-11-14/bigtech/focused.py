import pathlib,urllib.request,urllib.parse,re,html,datetime,json,concurrent.futures,xml.etree.ElementTree as E
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-14/bigtech')
qs={'asia_primary':'Alphabet Singapore Hong Kong bonds site:sgx.com OR site:hkex.com.hk OR site:abc.xyz after:2026-11-10', 'anthropic_pricing':'Anthropic IPO priced final price after:2026-11-13', 'customer_cuts':'Alphabet Meta Microsoft Amazon capex cut cancelled data center after:2026-11-13'}
us={n:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for n,q in qs.items()}
a=json.loads((p/'news_manifest.json').read_text());d={x['name']:x for x in a}
for n,g,i in [('asia_straits','news_asia',11),('asia_standard','news_asia',9),('asia_channel','news_asia',1),('asia_aol','news_asia',19),('anthropic_inkl','news_anthropic',21),('broadcom_redburn','news_broadcom',5)]:us[n+'_link']=d[g]['items'][i]['url']
def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);items=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:15]:items.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':items,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(f,us.items()));(p/'focused_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
