import datetime as dt,json,pathlib,re
from zoneinfo import ZoneInfo
P=pathlib.Path('/private/tmp/optics-nov17-market');TZ=ZoneInfo('Asia/Shanghai');ET=ZoneInfo('America/New_York')
q={}
for sym,body in re.findall(r'v_us([^=]+)="([^"]*)"',(P/'quotes.raw').read_bytes().decode('gb18030')):
 a=body.split('~');assert a[30].startswith('2026-11-16')
 t=dt.datetime.fromisoformat(a[30]).replace(tzinfo=ET)
 q[sym]=dict(symbol=sym,name=a[1],regular_close=float(a[3]),previous_regular_close=float(a[4]),open=float(a[5]),regular_change_pct=float(a[32]),high=float(a[33]),low=float(a[34]),session_date='2026-11-16',session='regular_close',currency='USD'if sym!='.IXIC'else None,source_last_update_exchange=t.isoformat(),source_last_update_beijing=t.astimezone(TZ).isoformat(),source='quotes.raw')
sina={}
for sym,body in re.findall(r'hq_str_gb_(\w+)="([^"]*)"',(P/'sina.raw').read_bytes().decode('gb18030')):
 a=body.split(',');sina[sym.upper()]=a
for sym in ['LITE','MRVL','COHR','CIEN','AAOI','FN','NVDA','AVGO']:
 a=sina[sym];r=q[sym]
 assert abs(float(a[1])-r['regular_close'])<.001 and a[25]=='Nov 16 04:00PM EST'
 r['sina_crosscheck']=dict(regular_close=float(a[1]),regular_change_pct=float(a[2]),regular_close_label_exchange=a[25],provider_update_beijing=a[3],source='sina.raw')
 assert a[24].endswith(' EST');at=dt.datetime.strptime('2026 '+a[24][:-4],'%Y %b %d %I:%M%p').replace(tzinfo=ET)
 assert at.date().isoformat()=='2026-11-16' and at.hour>=16
 r['afterhours']=dict(price=float(a[21]),change_vs_regular_close_pct=float(a[22]),time_exchange=at.isoformat(),time_beijing=at.astimezone(TZ).isoformat(),session='afterhours',source='sina.raw',snapshot_not_final=True)
 r['close_vs_open_pct']=(r['regular_close']/r['open']-1)*100;r['ohlc_does_not_establish_intraday_path']=True
 if sym in ['LITE','MRVL','COHR','CIEN','AAOI','FN']:
  h=json.loads((P/f'history_{sym}.raw').read_text())['data']['us'+sym];rows=h.get('day',h.get('qfqday',[]));dates=[x[0]for x in rows]
  r['historical_rows_returned']=len(rows);r['historical_dates_returned']=dates;r['five_twenty_day_return']=None;r['historical_gap']='Requested40 daily rows; returned sparse dates, not enough contiguous daily observations for verified5/20session returns.'
a=sina['SOX'];q['SOX']=dict(symbol='SOX',name=a[0],regular_close=float(a[1]),regular_change_pct=float(a[2]),previous_regular_close=float(a[26]),open=float(a[5]),high=float(a[6]),low=float(a[7]),session_date='2026-11-16',session='regular_session_index_value',provider_update_beijing=a[3],provider_exchange_label=a[25],source='sina.raw',afterhours=None,note='Index dissemination timestamp after16:00ET is not an after-hours traded session. Independent second SOX index provider not obtained; SOXX ETF is distinct.')
assert abs(sina['IXIC']and float(sina['IXIC'][1])-q['.IXIC']['regular_close'])<.01
q['.IXIC']['sina_crosscheck']=dict(regular_close=float(sina['IXIC'][1]),regular_change_pct=float(sina['IXIC'][2]),provider_update_beijing=sina['IXIC'][3],provider_exchange_label=sina['IXIC'][25])
(P/'analysis.json').write_text(json.dumps(q,ensure_ascii=False,indent=2))
print(json.dumps({k:dict(close=v['regular_close'],change=v['regular_change_pct'],afterhours=v.get('afterhours'),close_vs_open_pct=v.get('close_vs_open_pct'))for k,v in q.items()},ensure_ascii=False,indent=2))
