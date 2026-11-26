import concurrent.futures as cf,datetime as dt,json,pathlib,urllib.request
P=pathlib.Path('/private/tmp/eoptolink-20261117-1430-overseas')
urls={'asus_press':'https://press.asus.com/news/press-releases/','asus_server_news':'https://servers.asus.com/news','asus_sina':'https://finance.sina.cn/7x24/2026-11-17/detail-iniyznqf5439671.d.html'}
def get(x):
 n,u=x;s=dt.datetime.now(dt.timezone.utc).isoformat()
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=14) as r:b=r.read()
  (P/f'{n}.raw').write_bytes(b);return dict(id=n,url=u,ok=True,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),bytes=len(b))
 except Exception as e:return dict(id=n,url=u,ok=False,started_at=s,error=str(e))
with cf.ThreadPoolExecutor(max_workers=3) as e:r=list(e.map(get,urls.items()))
(P/'asus_manifest.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
