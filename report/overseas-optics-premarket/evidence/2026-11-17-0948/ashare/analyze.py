import json,re,datetime,hashlib
from pathlib import Path
from decimal import Decimal as D
from zoneinfo import ZoneInfo

p=Path('/private/tmp/optics-nov17-ashare')
root=Path('/Users/richao11/myproject/my-quant/report/overseas-optics-premarket')
state=json.loads((root/'state.json').read_text())
op=root/state['last_observation_file'];ob=json.loads(op.read_text())
prior={r['symbol']:r for r in ob['previous_a_share_session']['rows']}
date='2026-11-16';prevdate='2026-11-13';tz=ZoneInfo('Asia/Shanghai')
expected=[datetime.datetime(2026,11,16,9,30)+datetime.timedelta(minutes=5*i) for i in range(1,25)]+[datetime.datetime(2026,11,16,13)+datetime.timedelta(minutes=5*i) for i in range(1,25)]
names={'sz300502':'新易盛','sz300308':'中际旭创','sh515880':'通信ETF国泰','sz399006':'创业板指'}
rows=[]
for sym,name in names.items():
 data=json.loads((p/(sym+'-daily.json')).read_text())['data'][sym]
 daily=data.get('qfqday') or data.get('day')
 day=next(x for x in daily if x[0]==date);prev=next(x for x in daily if x[0]==prevdate)
 bars=json.loads(re.search(r'\((\[.*\])\)',(p/(sym+'-m5.txt')).read_text()).group(1))
 bars=[b for b in bars if b['day'].startswith(date)]
 assert [x['day'] for x in bars]==[t.strftime('%Y-%m-%d %H:%M:%S') for t in expected]
 o=D(bars[0]['open']);c=D(bars[-1]['close']);h=max(D(b['high']) for b in bars);l=min(D(b['low']) for b in bars);pc=D(prev[2]);tol=D('0.0051') if sym=='sz399006' else D('0.00001')
 checks={'complete_48_m5_bars':len(bars)==48,'m5_matches_daily':all(abs(x-y)<=tol for x,y in zip([o,c,h,l],[D(day[i]) for i in [1,2,3,4]])),'previous_daily_matches_archive':abs(pc-D(str(prior[sym]['close'])))<=tol}
 assert all(checks.values()),checks
 def intervals(value,key):
  a=[]
  for b in bars:
   if D(b[key])==value:
    end=datetime.datetime.fromisoformat(b['day']).replace(tzinfo=tz)
    a.append({'start':(end-datetime.timedelta(minutes=5)).isoformat(),'end':end.isoformat(),'exact_tick_time':None,key:float(value)})
  return a
 rows.append({'symbol':sym,'name':name,'session_date':date,'open':float(o),'high':float(h),'low':float(l),'close':float(c),'previous_close':float(pc),'change_pct':float((c/pc-1)*100),'opening_gap_pct':float((o/pc-1)*100),'close_vs_open_pct':float((c/o-1)*100),'daily_volume_change_pct':float((D(day[5])/D(prev[5])-1)*100),'regular_session_amount_yi_cny':float(sum(D(b['amount']) for b in bars)/D('1e8')),'regular_session_volume_shares_or_index_aggregate':float(sum(D(b['volume']) for b in bars)),'m5_high_intervals':intervals(h,'high'),'m5_low_intervals':intervals(l,'low'),'m5_complete_bars':len(bars),'crosscheck':checks,'raw_daily_bar':day,'raw_previous_daily_bar':prev,'raw_first_m5_bar':bars[0],'raw_final_m5_bar':bars[-1],'market_data_cutoff':'2026-11-16T15:00:00+08:00','current_day_data_excluded':True})
b={x['symbol']:x for x in rows}
rels={}
for k,x,y in [('eoptolink_minus_peer','sz300502','sz300308'),('eoptolink_minus_etf','sz300502','sh515880'),('eoptolink_minus_chinext','sz300502','sz399006'),('peer_minus_etf','sz300308','sh515880'),('peer_minus_chinext','sz300308','sz399006')]:rels[k]=b[x]['change_pct']-b[y]['change_pct']
review='上次11月16日报告倾向承压、偏弱震荡，实际新易盛、中际分别低开2.56%、3.47%，收166.80元（-11.08%）、408.97元（-12.28%），比开盘再跌8.74%、9.12%，均弱于通信ETF（-7.89%）及创业板（-4.37%）。承压方向相符，但“震荡”低估跌幅，不能把单次方向相符计作模型命中率。海外正常盘与A股收盘存在先后时序，价格数据不能证明下跌具体由哪条治理/监管消息或机构资金造成。'
a={'prepared_at':datetime.datetime.now(tz).isoformat(),'report_date':'2026-11-17','a_share_session_date':date,'data_cutoff_at':'2026-11-16T15:00:00+08:00','rows':rows,'relative_strength_pctpoints':rels,'prior_prediction_review':{'prior_date':'2026-11-16','prior_observation_file':str(op),'prior_observation_sha256':hashlib.sha256(op.read_bytes()).hexdigest(),'original_assessment':ob['assessment'],'assessment_zh':review,'no_hit_rate_estimate':True},'sources':json.loads((p/'manifest.json').read_text()),'limitations':['实际抓取在11月17日开盘后，API原始回复含今日栏位；本analysis只选11月16日完整日线、48根5分钟K线和11月13日比较基准，不使用今日数据。','高低点时点为5分钟区间，非首笔成交时间。','通信ETF为板块代理，不能代表全通信行业。','无直接交易所授权行情，仅公开第三方日线和分时一致性核对。','不读取或修改盘中监测state及任何预测。']}
(p/'analysis.json').write_text(json.dumps(a,ensure_ascii=False,indent=2))
print(json.dumps({'rows':[{k:x[k] for k in ['name','close','change_pct','open','opening_gap_pct','close_vs_open_pct','regular_session_amount_yi_cny','daily_volume_change_pct']} for x in rows],'relative':rels,'review':review},ensure_ascii=False,indent=2))
