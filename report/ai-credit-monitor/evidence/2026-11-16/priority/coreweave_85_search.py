import concurrent.futures, datetime, json, pathlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
p=pathlib.Path(__file__).parent
queries={
 'coreweave_85_recent':'CoreWeave "8.5" (debt OR loan OR financing) when:7d',
 'coreweave_85_official':'site:coreweave.com "8.5" financing',
 'coreweave_85_history':'CoreWeave "8.5 billion" financing',
}
def get(kq):
 k,q=kq
 u='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-US&gl=US&ceid=US:en'
 out={'name':k,'query':q,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15)
  b=r.read(); (p/(k+'.xml')).write_bytes(b)
  out.update(status=r.status,items=[{a:x.findtext(a) for a in ['title','pubDate','link']} for x in ET.fromstring(b).findall('.//item')][:25])
 except Exception as e:out['error']=str(e)
 return out
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:res=list(pool.map(get,queries.items()))
(p/'coreweave_85_search_manifest.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps(res,ensure_ascii=False,indent=2))
