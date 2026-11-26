import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/bigtech')
qs={"broadcom_anthropic":"Broadcom Anthropic financing $26 billion after:2026-11-09","bigtech_cds":"Alphabet Meta Microsoft Broadcom credit default swaps chipmakers November 10 2026","capex_cuts":"Google Meta Microsoft Amazon capex cut revised after:2026-11-09","alphabet_asia":"Alphabet Hong Kong Singapore bonds priced November 2026","microsoft_project":"Microsoft Oracle neocloud cancellation November 10 2026", "msft_china":"Microsoft Trump ban Chinese data center technology after:2026-11-09"}
us={n:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en' for n,q in qs.items()}
us.update({'google_carbon':'https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-carbon-now-available/','google_healthcare':'https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-for-healthcare/'})
def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'followup_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
