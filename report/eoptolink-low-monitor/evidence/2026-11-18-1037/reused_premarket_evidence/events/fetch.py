import urllib.request,json,concurrent.futures,datetime,re,html
from pathlib import Path
R=Path('/private/tmp/optics-nov18-events')
prev=Path('/Users/richao11/myproject/my-quant/report/overseas-optics-premarket/evidence/2026-11-17-0948/events')
m=json.loads((prev/'manifest.json').read_text())
urls={x['name']:x['url'] for x in m if ('submissions' in x['name'] or x['name'].endswith('_ir') or x['name']=='nvda_news') and not x['name'].startswith('cn_')}
urls.update({f'news_{i}':f'https://zhibo.sina.com.cn/api/zhibo/feed?zhibo_id=152&page={i}&page_size=100&type=0' for i in range(1,19)})
def get(x):
 name,url=x;at=datetime.datetime.now(datetime.timezone.utc).isoformat(); rec={'name':name,'url':url,'retrieved_at':at}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 OpticsResearch contact research@example.com'})
  with urllib.request.urlopen(req,timeout=20) as resp:b=resp.read();rec['status']=resp.status
  s=b.decode('utf-8',errors='replace');(R/(name+'.txt')).write_text(s);rec.update(ok=True,length=len(b))
 except Exception as e:rec.update(ok=False,error=str(e))
 return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:man=list(ex.map(get,urls.items()))
(R/'manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
print('FETCHED',len(man),'ok',sum(x['ok'] for x in man))
for x in man:
 if not x['ok']:print('GAP',x['name'],x['error'])
cut='2026-11-17T01:43:39'
fil=[]
for name in urls:
 if not name.endswith('submissions') or not (R/(name+'.txt')).exists():continue
 d=json.loads((R/(name+'.txt')).read_text());q=d['filings']['recent'];rows=[]
 for i,a in enumerate(q['accessionNumber']):
  if q['acceptanceDateTime'][i] > cut:rows.append({k:q[k][i] for k in ['accessionNumber','filingDate','acceptanceDateTime','form','primaryDocument']})
 fil.append({'symbol':name.split('_')[0].upper(),'cik':d['cik'],'new_filings':rows})
(R/'filings.json').write_text(json.dumps(fil,ensure_ascii=False,indent=2));print(json.dumps(fil,ensure_ascii=False,indent=2))
news=[]
pat='英伟达|黄仁勋|Marvell|迈威|Lumentum|Coherent|Ciena|Fabrinet|应用光电|新易盛|中际旭创|800G|1.6T|CPO|NPO|光模块|光通信|博通|微软|亚马逊|谷歌|Meta|CoreWeave|Nebius'
for p in R.glob('news_*.txt'):
 try:d=json.loads(p.read_text());rows=d['result']['data']['feed']['list']
 except Exception as e:print('newsparse',p.name,str(e));continue
 for row in rows:
  s=html.unescape(re.sub('<[^>]*>',' ',row.get('rich_text','') or row.get('content','')))
  dt=row.get('create_time','')
  if dt>'2026-11-17 09:43:39' and re.search(pat,s,re.I):news.append({'time':dt,'text':s,'id':row.get('id'),'link':row.get('docurl') or row.get('url'),'raw':row})
news.sort(key=lambda x:x['time']);(R/'news_matched.json').write_text(json.dumps(news,ensure_ascii=False,indent=2))
print('NEWS',len(news))
for row in news:print(row['time'],row['text'][:1500],row['link'])
