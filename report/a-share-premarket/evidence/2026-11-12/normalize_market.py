import json,re,shutil
from datetime import datetime,timezone
from pathlib import Path
B=Path('/private/tmp/a-share-premarket-2026-11-12');R=Path('/Users/richao11/myproject/my-quant/report/a-share-premarket');E=R/'evidence/2026-11-12'
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=load(B/'quote_manifest.json');prev=load(R/'2026-11-11.json')
us={}
for x in next(x for x in m if x['name']=='tencent_us')['quotes']:
 assert x['time'].startswith('2026-11-11')
 us[x['code']]=dict(name=x['name'],price=float(x['price']),previous_close=float(x['prev']),open=float(x['open']),change_pct=float(x['pct']),high=float(x['high']),low=float(x['low']),provider_timestamp=x['time'],market_session='2026-11-11',session='regular',note='Regular session close; provider update timestamp is not exchange closing instant.')
a={}
for name,code in [('tencent_kline_sh','sh000001'),('tencent_kline_sz','sz399001'),('tencent_kline_cyb','sz399006')]:
 d=load(B/(name+'.txt'))['data'][code]['day'];last,prior=d[-1],d[-2]
 assert last[0]=='2026-11-11' and prior[0]=='2026-11-10'
 a[code]=dict(market_session=last[0],name={'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指'}[code],open=float(last[1]),price=float(last[2]),previous_close=float(prior[2]),high=float(last[3]),low=float(last[4]),change_pct=round((float(last[2])/float(prior[2])-1)*100,2),source=next(x['url'] for x in m if x['name']==name),note='Historical day array only; exclude current-session embedded quote.')
def sina(name):return {x[1]:x[2].split(',') for x in re.finditer(r'var hq_str_([^=]+)="([^"]*)";', (B/name).read_text(encoding='utf-8'))}
f=sina('sina_us.txt')['gb_sox'];assert 'Nov 11' in f[25]
sox=dict(price=float(f[1]),change_pct=float(f[2]),market_session='2026-11-11',provider_updated_beijing=f[3],source='https://hq.sinajs.cn/list=gb_sox',instrument='Philadelphia_Semiconductor_Index_not_SOXX_ETF')
c=sina('sina_cross.txt');assets=[]
for code,label,unit in [('hf_CHA50CFD','A50 futures vendor indication','points'),('hf_CL','WTI futures vendor indication','USD_per_barrel'),('hf_GC','Gold futures vendor indication','USD_per_ounce')]:
 f=c[code];assert f[12]=='2026-11-12'
 assets.append(dict(name=label,value=float(f[0]),unit=unit,previous_vendor_settlement=float(f[7]),change_pct=(float(f[0])/float(f[7])-1)*100,quote_time_beijing=f[12]+'T'+f[6]+'+08:00',source='https://hq.sinajs.cn/list='+code,is_current_morning_quote=code!='hf_CHA50CFD',caveat='Vendor indication and reference settlement, not independently confirmed exchange direct.',latest_NVDA_news_reflected=False if code=='hf_CHA50CFD' else None))
for code,label in [('fx_susdcnh','USD/CNH'),('DINIW','Dollar index')]:
 f=c[code];assert f[-1]=='2026-11-12'
 assets.append(dict(name=label,value=float(f[8]),previous_vendor_close=float(f[3]),change_pct=(float(f[8])/float(f[3])-1)*100,quote_time_beijing=f[-1]+'T'+f[0]+'+08:00',source='https://hq.sinajs.cn/list='+code))
y=load(B/'cnbc_yields.txt')['FormattedQuoteResult']['FormattedQuote'][0]
assets.append(dict(name='US10Y Treasury electronic yield indication',value_pct=float(y['last'].rstrip('%')),quote_time_exchange=y['last_time'],source=next(x['url'] for x in m if x['name']=='cnbc_yields'),provider='CNBC Quote Cache / Tradeweb',regular_US_bond_market_Nov11_holiday=True,caveat='Electronic evening reference only; not Nov11 normal cash-bond closing yield or evidence of daily rate decline.'))
f=sina('sina_futures.txt')['hf_NQ']
assets.append(dict(name='Nasdaq futures vendor indication',value=float(f[0]),unit='points',previous_vendor_settlement=float(f[7]),change_pct=(float(f[0])/float(f[7])-1)*100,quote_time_beijing=f[12]+'T'+f[6]+'+08:00',source='https://hq.sinajs.cn/list=hf_NQ',caveat='Vendor indication, not exchange-direct NQ contract validation.'))
turnover=736154792000+940123794188
review=dict(available=True,forecast_file='2026-11-11.json',original_forecast=prev['forecast'],observed={k:dict(open_change_pct=(v['open']/v['previous_close']-1)*100,close_change_pct=v['change_pct'],close_below_open=v['price']<v['open']) for k,v in a.items()},assessment='开盘偏弱兑现，但全天主情景震荡分化低估科技反弹；低开高走备选情景兑现，创业板涨3.11%。',deviation_reason='昨日科技板块领涨、量能增长约11.4%，强于保守主情景；盘前未充分估计国内科技承接力度。11月11日美股收盘发生在A股收盘之后，不能倒因解释昨日A股。',numeric_hit_rate=None)
out=dict(prepared_at=datetime.now(timezone.utc).isoformat(),last_completed_us_session='2026-11-11',us_equities=us,sox=sox,a_share_previous_close=a,previous_sh_sz_turnover_yuan=turnover,previous_sh_sz_turnover_change_vs_prior_day_pct=(turnover/prev['previous_sh_sz_turnover_yuan']-1)*100,cross_assets=assets,previous_forecast_review=review,current_day_auction_quotes_excluded_from_prior_session=True)
E.mkdir(parents=True,exist_ok=True)
for file in B.iterdir():
 if file.is_file():shutil.copyfile(file,E/file.name)
(E/'market.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(sox=sox,A_previous=a,turnover=turnover,turnover_change_pct=out['previous_sh_sz_turnover_change_vs_prior_day_pct'],assets=assets),ensure_ascii=False,indent=2))
