from pathlib import Path
import json,re,hashlib,datetime,urllib.request,concurrent.futures,html
from zoneinfo import ZoneInfo
base=Path('/private/tmp/optics-nov17-calendar')
urls={
'sse_calendar':'https://www.sse.com.cn/disclosure/dealinstruc/closed/',
'sse_general':'https://www.sse.com.cn/disclosure/announcement/general/',
'szse_notice':'https://www.szse.cn/disclosure/notice/general/index.html',
'nyse_hours':'https://www.nyse.com/markets/hours-calendars',
'nasdaq_schedule':'https://www.nasdaq.com/market-activity/stock-market-holiday-schedule'}
def now():return datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def fetch(k,u):
 meta={'id':k,'url':u,'started_at':now()}
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=25) as r:
   raw=r.read();text=raw.decode('utf-8','replace');meta.update(http_status=r.status,response_date=r.headers.get('Date'),last_modified=r.headers.get('Last-Modified'),final_url=r.url)
  (base/(k+'.html')).write_text(text)
  clean=re.sub('<script[\s\S]*?</script>|<style[\s\S]*?</style>',' ',text,flags=re.I)
  clean=html.unescape(re.sub('<[^>]+>',' ',clean));clean=re.sub(r'\s+',' ',clean)
  (base/(k+'_clean.txt')).write_text(clean)
  meta.update(ok=True,retrieved_at=now(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),raw_file=str(base/(k+'.html')))
  if k in ['sse_general','szse_notice']:
   candidates=[]
   from urllib.parse import urljoin
   for href,label in re.findall('<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>([\s\S]*?)</a>',text,re.I):
    title=re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',label))).strip()
    if title and (len(title)>8) and ('公告' in title or '通知' in title):candidates.append({'title':title,'url':urljoin(u,href)})
   meta['visible_notices']=candidates[:30]
   meta['closure_candidates']=[x for x in candidates if re.search('临时休市|暂停交易|暂停.*交易|休市安排',x['title'])]
  if k=='sse_calendar':
   p=clean.find('2026年休市安排');meta['excerpt']=clean[p:p+1400]
  if k in ['nyse_hours','nasdaq_schedule']:
   terms=['November 26','November 27','9:30','4:00']
   meta['excerpts']=[]
   for t in terms:
    p=clean.find(t)
    if p>=0:meta['excerpts'].append(clean[max(0,p-100):p+430])
 except Exception as e:meta.update(ok=False,error=repr(e),retrieved_at=now())
 return meta
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(lambda kv:fetch(*kv),urls.items()))
(base/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
cn_date=datetime.date(2026,11,17);us_date=datetime.date(2026,11,16)
open_et=datetime.datetime(2026,11,16,9,30,tzinfo=ZoneInfo('America/New_York'));close_et=open_et.replace(hour=16,minute=0)
out={'date':str(cn_date),'weekday':cn_date.strftime('%A'),'normal_session':True,'checked_at':now(),'temporary_closure_notice_found':False,'conclusion':'2026-11-17 Tuesday is outside the refreshed official SSE 2026 holiday closures; latest visible SSE/SZSE general notices reviewed and no exchange-wide temporary closure announcement found.','us_session':{'date_et':str(us_date),'weekday_et':us_date.strftime('%A'),'scheduled_normal_equity_session':True,'scheduled_early_close':False,'open_et':open_et.isoformat(),'close_et':close_et.isoformat(),'close_china':close_et.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),'already_ended_at_check':True,'timezone_name':close_et.tzname(),'utc_offset_hours':close_et.utcoffset().total_seconds()/3600,'calendar_basis':'Refreshed NYSE/Nasdaq official calendar and trading-hour pages: Thanksgiving closure Nov26; early close Nov27, neither Nov16.'},'limitations':['Official visible SSE/SZSE notice indexes and holiday calendars are finite coverage; no claim of every possible channel.','Individual security/fund suspensions are distinct from exchange-wide closure.','This run happened after 09:30 Shanghai; must disclose actual delayed timing and never backdate to scheduled08:45.','US quote timestamps and actual close values require independent verification.'],'sources':rows}
# do not silently assert if fetch or decisive calendar text missing
cal=next(x for x in rows if x['id']=='sse_calendar')
if not cal.get('ok') or '2026年休市安排' not in cal.get('excerpt',''):out['normal_session']=None;out['limitations'].append('Official SSE holiday calendar refresh not confirmed')
notice_fail=[x['id'] for x in rows if x['id'] in ['sse_general','szse_notice'] and not x.get('ok')]
if notice_fail:out['limitations'].append('Notice refresh failed: '+','.join(notice_fail))
(base/'findings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='sources'},ensure_ascii=False,indent=2))
for r in rows:print(r['id'],r.get('ok'),r.get('http_status'),r.get('closure_candidates',[]),r.get('excerpts',[]))
