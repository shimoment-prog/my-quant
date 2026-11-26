import concurrent.futures as cf
import copy
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import urllib.request

R=pathlib.Path('/tmp/eoptolink-monitor-20261105-1030')
P=pathlib.Path('/Users/richao11/myproject/my-quant/report/eoptolink-low-monitor')
TZ=dt.timezone(dt.timedelta(hours=8))
EXPECTED_HASH='2c9fbe345e09ea6b4abc903c03be61584eb12036e0741570fd20d7656447b385'
pre=(P/'state.json').read_bytes()
assert hashlib.sha256(pre).hexdigest()==EXPECTED_HASH, 'State changed: reread before mutation'
state=json.loads(pre)
original=copy.deepcopy(state)
urls={
 'quotes_final.txt':'https://qt.gtimg.cn/q=sz300502,sz300308,sh515880,sz399006,sh000001',
 'sina_final.txt':'https://hq.sinajs.cn/list=sz300502,sz300308,sh515880,sz399006',
 'minute_final.json':'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sz300502',
 'm5_final.txt':'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_k=/CN_MarketDataService.getKLineData?symbol=sz300502&scale=5&ma=no&datalen=120',
}
def fetch(item):
 name,url=item
 start=dt.datetime.now(TZ).isoformat()
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
 with urllib.request.urlopen(req,timeout=15) as response:
  raw=response.read()
 (R/name).write_bytes(raw)
 return {'id':name.rsplit('.',1)[0],'name':name,'url':url,'ok':True,'started_at':start,'retrieved_at':dt.datetime.now(TZ).isoformat(),'bytes':len(raw)}
with cf.ThreadPoolExecutor(max_workers=4) as pool:
 final_manifest=list(pool.map(fetch,urls.items()))
(R/'manifest_final.json').write_text(json.dumps(final_manifest,ensure_ascii=False,indent=2))
sina=(R/'sina_final.txt').read_bytes().decode('gb18030')
quotes={}
for symbol,body in re.findall(r'hq_str_(\w+)="([^"]*)"',sina):
 f=body.split(',')
 time=f[30]+'T'+f[31]+'+08:00'
 price,previous=float(f[3]),float(f[2])
 q={'symbol':symbol,'name':f[0],'price':price,'previous_close':previous,'open':float(f[1]),'change_pct':round((price/previous-1)*100,5),'day_high':float(f[4]),'day_low':float(f[5]),'volume_shares':int(f[8]),'turnover_cny':float(f[9]),'quote_time':time,'field_asof':{k:time for k in ['price','change_pct','day_high','day_low','volume_shares','turnover_cny']},'exact_day_high_tick_time':None,'exact_day_low_tick_time':None,'source':'sina_final'}
 if symbol!='sz399006':
  q['vwap_derived']=float(f[9])/int(f[8])
  q['vwap_method']='cumulative turnover CNY / cumulative volume shares'
  q['field_asof']['vwap_derived']=time
 quotes[symbol]=q
q=quotes['sz300502']
now=dt.datetime.now(TZ).replace(microsecond=0)
assert now.date().isoformat()=='2026-11-05' and now.hour==10
age=(now-dt.datetime.fromisoformat(q['quote_time'])).total_seconds()
assert 0<=age<45, f'Quote too stale to freeze: {age}s'
assert q['day_low']==180.51 and 188<=q['price']<=196.5, f'Changed setup requires fresh review: {q}'
for x in quotes.values():
 assert x['quote_time'].startswith('2026-11-05')
tencent={}
for symbol,body in re.findall(r'v_(\w+)="([^"]*)"',(R/'quotes_final.txt').read_bytes().decode('gb18030')):
 f=body.split('~')
 tencent[symbol]={'price':float(f[3]),'previous_close':float(f[4]),'high':float(f[33]),'low':float(f[34]),'quote_time':dt.datetime.strptime(f[30],'%Y%m%d%H%M%S').replace(tzinfo=TZ).isoformat(),'change_pct':float(f[32])}
assert tencent['sz300502']['low']==q['day_low']

iso=now.isoformat(); date=now.date().isoformat(); stamp=now.strftime('%Y-%m-%d-%H%M')
obsrel=f'observations/{stamp}.json'; evrel=f'evidence/{stamp}'
assert not (P/obsrel).exists(), 'Observation exists; do not overwrite'
assert not (P/evrel).exists(), 'Evidence directory exists; do not overwrite'
L=q['day_low']; price=q['price']; vwap=q['vwap_derived']
deadline=now.replace(hour=15,minute=0,second=0).isoformat()
fixed=copy.deepcopy(state['fixed_reference'])
fixed.update(status='breached_recovered_at_latest_quote',last_verified_quote_time=q['quote_time'],last_verified_quote=price,last_verified_day_low=L,last_verified_session_date=date,below_fixed_line_now=price<179.83,below_fixed_line_at_last_verified_quote=price<179.83,previous_close_below_fixed_line=q['previous_close']<179.83,reclaimed_intraday_today=False,strict_breach_today=L<179.83,exact_today_reclaim_tick_time=None)
fixed['note']='Fixed179.83 was breached Nov3, exact first tick unknown. Today low180.51 is above179.83: no breach or reclaim today through quote time. Never reset the historical line.'
pred={'id':f'{stamp}-L{round(L*100)}','symbol':'300502.SZ','scheduled_check_at':date+'T10:30:00+08:00','triggered_at':'2026-11-05T10:29:09.345+08:00','created_at':iso,'forecast_start':iso,'snapshot_time':q['quote_time'],'threshold':L,'comparison':'strictly_less_than','event':f'Any traded price strictly below{L:.2f} after forecast_start and by deadline','deadline':deadline,'risk':'\u4e2d\u7b49','numeric_probability':None,'model_validated':False,'status':'pending','settled':False,'note':'Original actual creation time; not backdated to10:30. Independent intraday forecast. Threshold/start/deadline/risk remain immutable; settle only after expiry. Low available as of quoted snapshot; no tick stream between snapshot and creation.'}

bars_text=(R/'m5_final.txt').read_text()
bars=json.loads(bars_text[bars_text.index('['):bars_text.rindex(']')+1])
completed=[b for b in bars if b['day'].startswith(date) and dt.datetime.fromisoformat(b['day']).replace(tzinfo=TZ)<=dt.datetime.fromisoformat(q['quote_time'])]
lookup={b['day'][-8:]:b for b in completed}
comparisons=[]
for rise,pullback in [('09:55:00','10:00:00'),('10:10:00','10:15:00')]:
 a,b=lookup[rise],lookup[pullback]
 comparisons.append({'rise_bar':a,'pullback_bar':b,'turnover_change_pct':round((float(b['amount'])/float(a['amount'])-1)*100,4),'bar_length_minutes':5,'both_completed':True})
assert min(float(b['low']) for b in completed)==L
intraday={'completed_bars':completed,'latest_completed_bar_end':completed[-1]['day'],'low_interval_evidence':[b for b in completed if float(b['low'])==L],'swing_high_evidence':[lookup[t] for t in ['09:55:00','10:15:00','10:20:00','10:30:00']],'higher_pullback_area_evidence':[lookup[t] for t in ['10:05:00','10:15:00','10:25:00']],'equal_length_turnover_comparisons':comparisons,'interpretation_zh':'\u4ece180.51\u53cd\u5f39\uff0c\u4e3b\u8981\u9ad8\u70b9187.62\u2192188.47\u2192190.98\u2192192.40\u62ac\u9ad8\uff0c\u540e\u6765\u56de\u8e29\u533a\u57df183.38\u2192186.65\u2192189.89\u62ac\u9ad8\uff1b\u5e76\u975e\u6bcf\u6839bar\u5355\u8c03\u4e0a\u5347\u3002\u4e24\u4e2a\u5df2\u5b8c\u6210\u7b49\u957f\u56de\u8e29bar\u6210\u4ea4\u989d\u5206\u522b\u8f83\u524d\u4e00\u4e0a\u6da8bar\u7f29\u5c0f\u7ea618%\u548c22%\u3002','limitations':['\u672a\u5b8c\u6210bar\u4e0d\u7528\u4e8e\u6210\u4ea4\u989d\u5bf9\u6bd4\u3002','\u5206\u949f\u4ef7\u683c\u662f\u6837\u672c\uff1bbar\u6781\u503c\u4ec5\u8bc1\u660e\u6240\u5728\u533a\u95f4\uff0c\u4e0d\u80fd\u8ba4\u5b9a\u9996\u7b14\u6210\u4ea4\u65f6\u95f4\u3002','\u901a\u4fe1ETF515880\u4ec5\u4e3a\u677f\u5757\u4ee3\u7406\uff0c\u4e0d\u7b49\u4e8e\u5168\u901a\u4fe1\u884c\u4e1a\u6307\u6570\uff1b\u4e0d\u4ece\u4e3b\u52a8\u4e70\u5356\u6807\u7b7e\u63a8\u65ad\u673a\u6784\u6d41\u5165\u3002']}

audit=json.loads((R/'settlement_audit.json').read_text())
history=json.loads((R/'history.json').read_text())['data']['sz300502']
dailyrows=history.get('qfqday',history.get('day'))
yday=[b for b in dailyrows if b[0]=='2026-11-04'][0]
assert [float(yday[i]) for i in [1,2,3,4]]==[176.0,196.5,199.98,172.0]
settled=[]; pending=[]
by_id={a['prediction_id']:a for a in audit['predictions']}
for old in state['pending_predictions']:
 if dt.datetime.fromisoformat(old['deadline'])>=now:
  pending.append(old); continue
 a=by_id[old['id']]
 assert a['frozen_fields_match_state_and_observation'] and not a['already_settled_before_audit']
 assert old['forecast_start']==a['forecast_start'] and old['threshold']==a['threshold'] and old['deadline']==a['deadline']
 s=copy.deepcopy(old)
 s.update(status='settled',settled=True,resolved_at=iso,event_occurred=a['event_occurred'],closing_breach_occurred=a['closing_breach_occurred'],result='Strict trade breach within window' if a['event_occurred'] else 'No strict trade breach within window',resolution_evidence=copy.deepcopy(a))
 settled.append(s)
assert len(settled)==3
pending.append(pred)

q['distance_from_fixed_line_pct']=round((price/179.83-1)*100,5)
q['distance_above_day_low_pct']=round((price/L-1)*100,5)
q['fall_to_reach_day_low_pct']=round((L/price-1)*100,5)
q['above_vwap_pct']=round((price/vwap-1)*100,5)
risk={'risk':'\u4e2d\u7b49','numeric_probability':None,'probability_label':'\u6682\u65e0\u53ef\u9760\u767e\u5206\u6bd4','scope':'Only any trade strictly below this frozen180.51 low after actual start through today15:00; not an overall price forecast.','model_validated':False,'reasons':[
 f'\u5f53\u524d{price:.2f}\u9ad8\u4e8e\u51bb\u7ed3\u4f4e\u70b9{L:.2f}\u7ea6{q["distance_above_day_low_pct"]:.2f}%\uff1b\u56de\u843d\u81f3\u4f4e\u70b9\u9700\u8dcc{abs(q["fall_to_reach_day_low_pct"]):.2f}%\uff0c\u4e25\u683c\u8dcc\u7834\u9700\u66f4\u5927\u5e45\u5ea6\u3002',
 f'\u5f53\u524d\u9ad8\u4e8e\u7d2f\u8ba1\u6210\u4ea4\u5747\u4ef7{vwap:.2f}\u7ea6{q["above_vwap_pct"]:.2f}%\uff0c\u5df2\u5b8c\u62105\u5206\u949fbar\u663e\u793a\u53cd\u5f39\u9ad8\u70b9\u4e0e\u540e\u6765\u56de\u8e29\u533a\u57df\u62ac\u9ad8\uff0c\u6240\u67e5\u4e24\u4e2a\u7b49\u957f\u56de\u8e29\u6210\u4ea4\u989d\u7f29\u5c0f\u3002',
 f'\u65b0\u6613\u76db{q["change_pct"]:.2f}%\uff0c\u4e2d\u9645\u65ed\u521b{quotes["sz300308"]["change_pct"]:.2f}%\uff0c\u5f31\u4e8e\u521b\u4e1a\u677f{quotes["sz399006"]["change_pct"]:+.2f}%\u548c\u901a\u4fe1ETF{quotes["sh515880"]["change_pct"]:+.2f}%\uff0c\u5e76\u975e\u5149\u6a21\u5757\u6574\u4f53\u8f6c\u5f3a\u3002',
 '11\u67084\u65e5\u6d77\u5916\u516d\u53ea\u5149\u901a\u4fe1\u80a1\u5168\u90e8\u4e0b\u8dcc\u4e14\u5f31\u4e8e\u5e7f\u4e49\u7f8e\u80a1\uff0c\u6784\u6210\u4f30\u503c\u60c5\u7eea\u538b\u529b\uff1bCoherent\u76d8\u540e\u5b9e\u9645\u8425\u6536\u548c\u6307\u5f15\u589e\u957f\u5219\u4e0d\u652f\u6301\u76f4\u63a5\u8ba4\u5b9a\u5168\u884c\u4e1a\u9700\u6c42\u5df2\u574d\u584c\u3002',
 '\u8ddd\u79bb15:00\u4ecd\u6709\u4e0a\u5348\u4f59\u6bb5\u548c\u5b8c\u6574\u5348\u540e\u4ea4\u6613\uff0c\u4e0d\u80fd\u56e0\u6682\u65f6\u53cd\u5f39\u65ad\u8a00\u5f53\u65e5\u4e0d\u4f1a\u518d\u521b\u65b0\u4f4e\u3002'],
 'risk_increases_if':f'\u5931\u5b88\u8fd1\u671f\u56de\u8e29186.65\u53ca\u52a8\u6001\u5747\u4ef7\u7ea6{vwap:.2f}\uff0c\u4e14\u76f8\u90bb\u7b49\u957f\u5df2\u5b8c\u6210\u56de\u8e29bar\u6210\u4ea4\u989d\u653e\u5927\u3001\u4e2d\u9645\u65ed\u521b\u53ca\u901a\u4fe1ETF\u540c\u6b65\u8f6c\u5f31\u3002',
 'risk_decreases_if':'\u5b88\u4f4f188\u2014190\u533a\u57df\u3001\u7a81\u7834\u672c\u6b21\u5feb\u7167\u65e5\u9ad8\u540e\u56de\u8e29\u4f4e\u70b9\u7ee7\u7eed\u62ac\u9ad8\uff0c\u540c\u4e1a\u76f8\u5bf9\u5f3a\u5f31\u6539\u5584\uff1b\u8fd9\u4e9b\u662f\u6539\u53d8\u5224\u65ad\u7684\u6761\u4ef6\uff0c\u4e0d\u662f\u4fdd\u8bc1\u5b88\u4f4f\u3002',
 'intraday_review':intraday,'remaining_wall_clock_minutes':round((dt.datetime.fromisoformat(deadline)-now).total_seconds()/60,3),'remaining_active_trading_minutes_approx':round((dt.datetime.fromisoformat(deadline)-now).total_seconds()/60-90,3)}

overseas=json.loads((R/'overseas/updates.json').read_text())
calendar=json.loads((R/'calendar/calendar.json').read_text())
company={'new_announcement_found_in_reviewed_list':False,'latest_listed_date':'2026-11-03','latest_listed_title':'\u5173\u4e8e\u56de\u8d2d\u516c\u53f8\u80a1\u4efd\u7684\u8fdb\u5c55\u516c\u544a','list_source':'https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/300502.phtml','checked_at':next(x['retrieved_at'] for x in json.loads((R/'manifest.json').read_text()) if x['name']=='sina_announcements.html'),'limitations':'\u4ec5\u5df2\u8bfb\u53d6\u7684\u516c\u544a\u7d22\u5f15\uff0c\u975e\u6240\u6709\u6e20\u9053\u5b8c\u6574\u6027\u4fdd\u8bc1\u3002\u4e1c\u65b9\u8d22\u5bcc\u516c\u544aAPI HTTP567\u3002\u65e7\u56de\u8d2d\u516c\u544a\u4e0d\u662f\u4eca\u65e5\u65b0\u8ba2\u5355\u6216\u4fdd\u8bc1\u6258\u5e95\u3002'}
sources=[]
for x in json.loads((R/'manifest.json').read_text())+final_manifest:
 x=copy.deepcopy(x); x['raw_evidence_file']=evrel+'/'+x['name'] if x['ok'] else None
 sources.append(x)
obs={'schema_version':1,'automation_id':'10-30','triggered_at':pred['triggered_at'],'scheduled_at':pred['scheduled_check_at'],'observed_at':iso,'session':'intraday','scheduled_check':True,'trading_day':calendar,'quotes':quotes,'crosscheck_tencent':tencent,'quote_age_seconds_at_forecast_creation':age,'fixed_reference':fixed,'frozen_prediction':pred,'risk_assessment':risk,'overseas':overseas,'company_disclosures':company,'settled_predictions':settled,'settlement_audit':{'checked_at':iso,'newly_settled_count':len(settled),'previously_completed_count':state['completed_prediction_count'],'audit_file':evrel+'/settlement_audit.json','all_original_frozen_fields_preserved':True,'no_hit_rate':'Qualitative heterogeneous event assessments with tiny sample; no statistical hit rate.'},'pending_predictions':pending,'sources':sources,'data_gaps':['\u6682\u65e0\u9002\u7528\u4e8e\u672c\u6b21\u4e8b\u4ef6\u548c\u65f6\u6bb5\u4e14\u7ecf\u8fc7\u9a8c\u8bc1\u7684\u7edf\u8ba1\u6982\u7387\u6a21\u578b\u3002','\u65e5\u9ad8/\u65e5\u4f4e\u9010\u7b14\u5f62\u6210\u65f6\u95f4\u548c179.83\u9996\u6b21\u8dcc\u7834\u65f6\u95f4\u672a\u77e5\uff1b\u5206\u949f\u6837\u672c\u6216bar\u4e0d\u80fd\u5f53\u9996\u7b14\u6210\u4ea4\u3002','\u5feb\u7167\u4e0e\u5b9e\u9645\u521b\u5efa\u4e4b\u95f4\u6ca1\u6709\u9010\u7b14\u6d41\uff0c\u884c\u60c5\u65f6\u70b9\u548c\u79d2\u7ea7\u5dee\u8ddd\u5df2\u5355\u72ec\u4fdd\u5b58\u3002','\u4e1c\u65b9\u8d22\u5bcc\u516c\u544aAPI HTTP567\uff1b\u65b0\u6d6a\u516c\u544a\u7d22\u5f15\u53ef\u7528\uff0c\u4f46\u4e0d\u4fdd\u8bc1\u5168\u6e20\u9053\u5b8c\u6574\u6027\u3002','\u6d77\u5916\u516d\u5bb6\u516c\u53f8\u6838\u67e5\u6709\u8fb9\u754c\uff0c\u672a\u53d6\u5f97\u65b0\u6613\u76db\u7279\u5b9a\u4e22\u5355\u8bc1\u636e\uff0c\u4e0d\u80fd\u8bc1\u660e\u6240\u6709\u8ba2\u5355\u5747\u65e0\u53d8\u5316\u3002'],'notification':{'decision':'NOTIFY','prepared_at':iso,'delivery_status':'prepared_for_final_response','reason':'User explicitly requests each10:30/14:30normal-session report, including unchanged risk.'},'raw_evidence_directory':evrel}

all_settled={x['id']:x for x in state.get('settled_predictions',[])}
for x in state.get('last_settled_predictions',[]): all_settled.setdefault(x['id'],x)
for x in settled:
 assert x['id'] not in all_settled, 'Never settle twice'
 all_settled[x['id']]=x
state.update(fixed_reference=fixed,last_run_at=iso,last_observation_file=obsrel,pending_predictions=pending,settled_predictions=list(all_settled.values()),last_settled_predictions=settled,completed_prediction_count=state['completed_prediction_count']+len(settled),last_notified_at=iso,last_notified_risk='\u4e2d\u7b49',last_notification_status='NOTIFY',last_market_assessment_at=iso,last_notification_type='scheduled_intraday_risk_report',last_notification_delivery_status='prepared_for_final_response')
assert state['completed_prediction_count']==4 and len(state['pending_predictions'])==1
for s in settled:
 old=next(x for x in original['pending_predictions'] if x['id']==s['id'])
 for k in ['created_at','forecast_start','snapshot_time','threshold','deadline','risk']:
  assert old[k]==s[k], (s['id'],k)
assert state['fixed_reference']['price']==179.83
assert (P/'state.json').read_bytes()==pre, 'State changed during fetch; abort rather than overwrite'

# Preserve raw inputs before writing the new immutable observation, then atomically replace state.
evidence=P/evrel
shutil.copytree(R,evidence,ignore=shutil.ignore_patterns('finalize.py','__pycache__'))
(evidence/'state_before.json').write_bytes(pre)
(evidence/'original_observation_sha256.json').write_text(json.dumps({str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (P/'observations').glob('*.json')},indent=2))
with (P/obsrel).open('x') as f: json.dump(obs,f,ensure_ascii=False,indent=2)
state_tmp=P/'state.json.next'
state_tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
state_tmp.replace(P/'state.json')
summary={'observation':str(P/obsrel),'created_at':iso,'quote_time':q['quote_time'],'quote_age_seconds':age,'price':price,'pct':q['change_pct'],'high':q['day_high'],'low':L,'vwap':vwap,'amount_yi':q['turnover_cny']/1e8,'above_fixed_pct':q['distance_from_fixed_line_pct'],'above_low_pct':q['distance_above_day_low_pct'],'fall_to_low_pct':q['fall_to_reach_day_low_pct'],'peer_pct':quotes['sz300308']['change_pct'],'etf_pct':quotes['sh515880']['change_pct'],'chinext_pct':quotes['sz399006']['change_pct'],'risk':'\u4e2d\u7b49','settled_count':len(settled),'completed_count':state['completed_prediction_count'],'latest_completed_bar':completed[-1]}
(R/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
