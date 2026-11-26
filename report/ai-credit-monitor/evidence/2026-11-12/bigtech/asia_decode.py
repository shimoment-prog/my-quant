import json,re,pathlib,urllib.request,urllib.parse,datetime,concurrent.futures
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-12/bigtech')
def f(n):
 s=(p/(n+'.html')).read_text();id=re.search('data-n-a-id="([^"]+)"',s)[1];ts=re.search('data-n-a-ts="([^"]+)"',s)[1];sg=re.search('data-n-a-sg="([^"]+)"',s)[1]
 inner=["garturlreq",[["X","X",["X","X"],None,None,1,1,"US:en",None,1,None,None,None,None,None,0,None,None,[1608992183,723341000]],"X","X",1,[2,3,4,8],1,0,"655000234",0,0,None,0],id,int(ts),sg]
 data=urllib.parse.urlencode({'f.req':json.dumps([[["Fbv4je",json.dumps(inner),None,"generic"]]])}).encode()
 u='https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je'
 try:
  b=urllib.request.urlopen(urllib.request.Request(u,data=data,headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}),timeout=20).read();s=b.decode();(p/(n+'_decoded.txt')).write_text(s);return {'name':n,'result':s[:2500]}
 except Exception as e:return {'name':n,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=2).map(f,['asia_investing_link','asia_reuters_link']));(p/'asia_decode_manifest.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
