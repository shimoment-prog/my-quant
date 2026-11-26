import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import pathlib
import urllib.request

P=pathlib.Path('/private/tmp/eoptolink-20261117-1430-overseas')
urls={f'news_{i}':f'https://zhibo.sina.com.cn/api/zhibo/feed?zhibo_id=152&page={i}&page_size=100&type=0' for i in range(1,7)}
urls.update(mrvl_ir='https://investor.marvell.com/news-events/press-releases',nvda_news='https://nvidianews.nvidia.com/news',sse_general='https://www.sse.com.cn/disclosure/announcement/general/',szse_general='https://www.szse.cn/disclosure/notice/general/index.html')
def fetch(x):
 n,u=x;s=dt.datetime.now(dt.timezone.utc).isoformat()
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=18) as r:
   b=r.read();status=r.status
  (P/f'{n}.raw').write_bytes(b)
  return dict(id=n,url=u,started_at=s,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),status=status,ok=True,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
 except Exception as e:return dict(id=n,url=u,started_at=s,ok=False,error=str(e))
with cf.ThreadPoolExecutor(max_workers=10) as pool:rows=list(pool.map(fetch,urls.items()))
(P/'manifest.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
