import concurrent.futures,datetime,json,urllib.request,urllib.parse
from pathlib import Path
p=Path(__file__).parent
codes=['603986','300750','300502','300308','000858','600519']
cut='2026-11-13 08:45:00'
def get(c):
 u='https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=50&page_index=1&ann_type=A&client_source=web&stock_list='+c
 r={'code':c,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as h:d=h.read()
  (p/'raw'/(c+'.json')).write_bytes(d);j=json.loads(d);li=j.get('data',{}).get('list',[])
  r.update(ok=True,new_items=[x for x in li if x.get('display_time','')>cut],latest_items=[{k:x.get(k) for k in ['title','art_code','notice_date','display_time']} for x in li[:2]])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:rs=list(ex.map(get,codes))
(p/'raw'/'manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
u='https://qt.gtimg.cn/q='+','.join(('sh' if c[0]=='6' else 'sz')+c for c in codes)
r={'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
try:
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as h:d=h.read()
 (p/'raw'/'quotes.txt').write_bytes(d);r.update(ok=True,text=d.decode('gbk','replace'))
except Exception as e:r.update(ok=False,error=str(e))
(p/'raw'/'quotes_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False))
