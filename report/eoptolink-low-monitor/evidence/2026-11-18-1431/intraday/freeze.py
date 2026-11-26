from pathlib import Path
from datetime import datetime,timedelta,timezone
import concurrent.futures as cf,json,re,urllib.request
R=Path('/private/tmp/eoptolink-monitor-20261118-1430');TZ=timezone(timedelta(hours=8))
urls={'sina_final.txt':'https://hq.sinajs.cn/list=sz300502,sz300308,sh515880,sz399006','quotes_final.txt':'https://qt.gtimg.cn/q=sz300502,sz300308,sh515880,sz399006','m5_final.txt':'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol=sz300502&scale=5&ma=no&datalen=120'}
def fetch(item):
 n,u=item;start=datetime.now(TZ)
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=12)as res:b=res.read()
  (R/n).write_bytes(b)
  return dict(name=n,url=u,ok=True,retrieved_at=datetime.now(TZ).isoformat(),started_at=start.isoformat())
 except Exception as e:return dict(name=n,url=u,ok=False,error=str(e),started_at=start.isoformat())
with cf.ThreadPoolExecutor(max_workers=3)as ex:manifest=list(ex.map(fetch,urls.items()))
(R/'manifest_final.json').write_text(json.dumps(manifest,indent=2))
assert all(x['ok']for x in manifest)
quotes={}
for sym,raw in re.findall(r'var hq_str_(\w+)="([^"]*)";', (R/'sina_final.txt').read_bytes().decode('gb18030')):
 x=raw.split(',');t=x[30]+'T'+x[31]+'+08:00';vol=float(x[8]);amt=float(x[9]);price=float(x[3]);prev=float(x[2]);high=float(x[4]);low=float(x[5])
 quotes[sym]=dict(name=x[0],symbol=sym,price=price,previous_close=prev,open=float(x[1]),change_pct=(price/prev-1)*100,day_high=high,day_low=low,volume_shares=vol,amount_cny=amt,vwap=amt/vol if vol and sym!='sz399006' else None,quote_time=t,source='sina_final.txt',currency='CNY'if sym!='sz399006'else'index_points',field_times=dict(price=t,change_pct=t,day_high_cumulative_through=t,day_low_cumulative_through=t,amount_cumulative_through=t,vwap_cumulative_through=t if sym!='sz399006' else None),exact_high_tick_time=None,exact_low_tick_time=None,vwap_method='cumulative amount(CNY) / cumulative volume(shares)'if sym!='sz399006'else'not applicable to index',distance_from_fixed_line_yuan=price-179.83 if sym=='sz300502'else None,distance_from_fixed_line_pct=(price/179.83-1)*100 if sym=='sz300502'else None,distance_above_day_low_yuan=price-low,distance_above_day_low_pct=(price/low-1)*100)
cross={}
for sym,raw in re.findall(r'v_(\w+)="([^"]*)";', (R/'quotes_final.txt').read_bytes().decode('gb18030')):
 x=raw.split('~');cross[sym]=dict(price=float(x[3]),day_high=float(x[33]),day_low=float(x[34]),quote_time=datetime.strptime(x[30],'%Y%m%d%H%M%S').replace(tzinfo=TZ).isoformat(),source='quotes_final.txt')
q=quotes['sz300502'];now=datetime.now(TZ).replace(microsecond=0);qt=datetime.fromisoformat(q['quote_time'])
assert now.date().isoformat()=='2026-11-18'and (14,30)<=(now.hour,now.minute)<(15,0)
assert 0<=(now-qt).total_seconds()<60 and qt.date()==now.date()
assert cross['sz300502']['day_low']==q['day_low']
assert abs(cross['sz300502']['price']/q['price']-1)<.003
assert q['price']<q['vwap'] and 1.5<q['distance_above_day_low_pct']<3 and q['price']<179.83
assert q['change_pct']<quotes['sh515880']['change_pct']and q['change_pct']<quotes['sz399006']['change_pct']
L=q['day_low'];deadline=now.replace(hour=15,minute=0,second=0)
pred=dict(id=now.strftime('%Y-%m-%d-%H%M')+'-L'+str(round(L*100)),symbol='300502.SZ',scheduled_check_at='2026-11-18T14:30:00+08:00',triggered_at='2026-11-18T14:28:38.800+08:00',created_at=now.isoformat(),forecast_start=now.isoformat(),snapshot_time=q['quote_time'],threshold=L,comparison='strictly_less_than',event=f'Any traded price strictly below{L:.2f} after forecast_start and by deadline',deadline=deadline.isoformat(),risk='中等',numeric_probability=None,model_validated=False,status='pending',settled=False,note='Independent afternoon forecast starts at actual creation, not scheduled14:30 or early heartbeat. Original morning155.55 forecast remains unchanged until15:00. Current price belowVWAP and relatively weak after lower rebound highs, but over1.5percent above newly frozen cumulative low and short remaining window plus nonpersistent pullback volume mitigate risk. Overnight overseas recovery is old context; newly reported short-seller allegations are unverified risk sentiment, not proof of violation or cancelled orders. No tickstream in quote-to-creation gap; never alter threshold/window/risk later.')
s=(R/'m5_final.txt').read_text();bars=json.loads(s[s.index('['):s.rindex(']')+1]);today=[x for x in bars if x['day'].startswith('2026-11-18')]
structural_cutoff=min(datetime.fromisoformat(x['retrieved_at'])for x in manifest if x['ok'])
completed=[x for x in today if datetime.fromisoformat(x['day']).replace(tzinfo=TZ)<=structural_cutoff]
unfinished=[x for x in today if x not in completed]
assert len(completed)>=42 and max(float(x['high'])for x in completed)==163.35 and min(float(x['low'])for x in completed)>=L
snap=dict(stamp=now.strftime('%Y-%m-%d-%H%M'),quotes=quotes,crosscheck_tencent=cross,quote_age_seconds=(now-qt).total_seconds(),frozen_prediction=pred,completed_bars=completed,excluded_unfinished_bars=unfinished,structural_bar_cutoff=datetime.fromisoformat(completed[-1]['day']).replace(tzinfo=TZ).isoformat(),source_timing_note='Structure uses completed m5_final bars available before forecast creation; unfinished bars excluded. Final quote precedes actual forecast; all source and actual creation times preserved. Later progress/research cannot alter original risk/threshold/window.')
for name,obj in [('snapshot.json',snap),('frozen_prediction.json',pred)]:
 with (R/name).open('x')as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'forecast':pred,'quotes':quotes,'completed_bar_count':len(completed),'excluded_unfinished':unfinished,'quote_age_seconds':(now-qt).total_seconds()},ensure_ascii=False,indent=2))
