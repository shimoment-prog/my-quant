import pathlib,urllib.request,urllib.parse,re,html,datetime,json,concurrent.futures,xml.etree.ElementTree as E
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-18/bigtech')
us={'anthropic_s1a':'https://www.sec.gov/Archives/edgar/data/2130357/000162828026074338/anthropicpbc-sx1ax3.htm','anthropic_8a':'https://www.sec.gov/Archives/edgar/data/2130357/000162828026074342/anthropic-8xa12b.htm','anthropic_guide':'https://www.cnbc.com/2026/11/16/anthropic-ipo-date-price-range.html','broadcom_ir':'https://investors.broadcom.com/news-events/press-releases','bis_release':'https://www.bis.gov/press-release/bis-issues-rule-addressing-remote-access-american-super-intelligence-technology','bis_pdf':'https://www.bis.gov/media/documents/rin-0694-ak50.pdf'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  if '_rss' in n or n.startswith('news'):
   try:
    for x in E.fromstring(raw).findall('./channel/item')[:30]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
   except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'incremental_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
