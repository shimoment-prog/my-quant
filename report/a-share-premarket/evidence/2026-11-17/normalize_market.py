import json,re
from pathlib import Path
from datetime import datetime,timezone
E=Path(__file__).resolve().parent
R=E.parent.parent
load=lambda p:json.loads(p.read_text())
m=load(E/'quote_manifest.json');prev=load(R/'2026-11-16.json')
us={}
for x in next(x for x in m if x['name']=='tencent_us')['quotes']:
 assert x['time'].startswith('2026-11-16'),x
 us[x['code']]=dict(name=x['name'],price=float(x['price']),previous_close=float(x['prev']),open=float(x['open']),change_pct=float(x['pct']),high=float(x['high']),low=float(x['low']),provider_timestamp=x['time'],market_session='2026-11-16',session='regular',note='Close of complete regular session; update timestamp may be later than closing instant.')
a={}
for name,code in [('tencent_kline_sh','sh000001'),('tencent_kline_sz','sz399001'),('tencent_kline_cyb','sz399006')]:
 d=load(E/(name+'.txt'))['data'][code]['day'];last,prior=d[-1],d[-2]
 assert last[0]=='2026-11-16' and prior[0]=='2026-11-13'
 a[code]=dict(market_session=last[0],name={'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指'}[code],open=float(last[1]),price=float(last[2]),previous_close=float(prior[2]),high=float(last[3]),low=float(last[4]),change_pct=round((float(last[2])/float(prior[2])-1)*100,2),source=next(x['url'] for x in m if x['name']==name),note='Historical daily array only; current quotes excluded.')
def sina(name):return {x[1]:x[2].split(',') for x in re.finditer(r'var hq_str_([^=]+)="([^"]*)";', (E/name).read_text())}
f=sina('sina_us.txt')['gb_sox'];assert 'Nov 16' in f[25]
sox=dict(price=float(f[1]),change_pct=float(f[2]),market_session='2026-11-16',provider_updated_beijing=f[3],source='https://hq.sinajs.cn/list=gb_sox')
c=sina('sina_cross.txt');assets=[]
for code,label,unit in [('hf_CHA50CFD','A50 futures vendor indication','points'),('hf_CL','WTI futures vendor indication','USD_per_barrel'),('hf_GC','Gold futures vendor indication','USD_per_ounce'),('hf_OIL','Brent futures vendor indication','USD_per_barrel')]:
 f=c[code];assert f[12]=='2026-11-17'
 assets.append(dict(name=label,value=float(f[0]),unit=unit,previous_vendor_settlement=float(f[7]),change_pct=(float(f[0])/float(f[7])-1)*100,quote_time_beijing=f[12]+'T'+f[6]+'+08:00',source='https://hq.sinajs.cn/list='+code,phase='after_A_share_open',caveat='Vendor reference, not independently matched exchange contract or official settlement.'))
for code,label in [('fx_susdcnh','USD/CNH'),('DINIW','Dollar index')]:
 f=c[code];assert f[-1]=='2026-11-17'
 assets.append(dict(name=label,value=float(f[8]),previous_vendor_close=float(f[3]),change_pct=(float(f[8])/float(f[3])-1)*100,quote_time_beijing=f[-1]+'T'+f[0]+'+08:00',source='https://hq.sinajs.cn/list='+code,phase='after_A_share_open'))
y=load(E/'cnbc_yields.txt')['FormattedQuoteResult']['FormattedQuote'][0]
assets.append(dict(name='US10Y Treasury electronic yield indication',value_pct=float(y['last'].rstrip('%')),previous_vendor_reference_pct=float(y['previous_day_closing'].rstrip('%')),change_bp_vs_vendor_reference=(float(y['last'].rstrip('%'))-float(y['previous_day_closing'].rstrip('%')))*100,quote_time_exchange=y['last_time'],source=next(x['url'] for x in m if x['name']=='cnbc_yields'),provider='CNBC Quote Cache / Tradeweb',phase='after_A_share_open',caveat='Electronic quote not official daily yield; reference change not full US cash-session move.'))
f=sina('sina_futures.txt')['hf_NQ'];assert f[12]=='2026-11-17'
assets.append(dict(name='Nasdaq futures vendor indication',value=float(f[0]),unit='points',previous_vendor_settlement=float(f[7]),change_pct=(float(f[0])/float(f[7])-1)*100,quote_time_beijing=f[12]+'T'+f[6]+'+08:00',source='https://hq.sinajs.cn/list=hf_NQ',phase='after_A_share_open',caveat='Vendor reference, not independently matched exchange contract.'))
now={}
for x in next(x for x in m if x['name']=='tencent_a')['quotes']:
 assert x['time'].startswith('20261117'),x
 now[x['code']]=dict(name=x['name'],price=float(x['price']),previous_close=float(x['prev']),open=float(x['open']),open_change_pct=(float(x['open'])/float(x['prev'])-1)*100,change_pct=float(x['pct']),high=float(x['high']),low=float(x['low']),provider_time_beijing=x['time'],phase='intraday_after_open',source='https://qt.gtimg.cn/q='+x['code'])
review=dict(available=True,forecast_file='2026-11-16.json',original_forecast=prev['forecast'],observed={k:dict(open_change_pct=(v['open']/v['previous_close']-1)*100,close_change_pct=v['change_pct'],close_below_open=v['price']<v['open'],low_broke_forecast_downside_threshold=v['low']<prev['a_share_previous_close'][k]['low']) for k,v in a.items()},assessment='11月16日沪指低开约0.63%、创业板低开约1.26%，下跌方向较原平开偏弱更弱；全天沪指跌0.87%、创业板跌4.37%，主情景中的震荡反抽持续性明显高估，下破此前低点的承压备选成立。',deviation_reason='科技板块承接弱于预期；11月16日美国收盘晚于A股，不能倒因作为此前A股下跌原因。经济数据影响另需官方发布时间核对，不作未经证实资金流归因。',numeric_hit_rate=None)
out=dict(prepared_at=datetime.now(timezone.utc).isoformat(),report_date='2026-11-17',last_completed_us_session='2026-11-16',us_equities=us,sox=sox,a_share_previous_close=a,cross_assets=assets,current_A_share_intraday=now,previous_forecast_review=review,late_delivery=True,preopen_cross_assets_snapshot_available=False,current_day_quotes_excluded_from_prior_session=True)
(E/'market.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(A_previous=a,cross_assets=assets,current_A=now,review=review),ensure_ascii=False,indent=2))
