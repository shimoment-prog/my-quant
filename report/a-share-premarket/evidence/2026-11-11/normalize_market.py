import json,re
from pathlib import Path
from datetime import datetime,timezone
B=Path('/private/tmp/a-share-premarket-2026-11-11');R=Path('/Users/richao11/myproject/my-quant/report/a-share-premarket')
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=load(B/'quote_manifest.json');prev=load(R/'2026-11-10.json')
us={}
for r in next(x for x in m if x['name']=='tencent_us')['quotes']:
 assert r['time'].startswith('2026-11-10')
 us[r['code']]=dict(name=r['name'],price=float(r['price']),previous_close=float(r['prev']),open=float(r['open']),change_pct=float(r['pct']),high=float(r['high']),low=float(r['low']),provider_timestamp=r['time'],market_session='2026-11-10',price_scope='regular_session_close_confirmed_by_news_for_indices_not_provider_update_time_equals_close')
a={}
for n,code in [('tencent_kline_sh','sh000001'),('tencent_kline_sz','sz399001'),('tencent_kline_cyb','sz399006')]:
 j=load(B/(n+'.txt'));d=j['data'][code]['day'];last,prior=d[-1],d[-2]
 assert last[0]=='2026-11-10' and prior[0]=='2026-11-09'
 a[code]=dict(market_session=last[0],name={'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指'}[code],open=float(last[1]),price=float(last[2]),previous_close=float(prior[2]),high=float(last[3]),low=float(last[4]),change_pct=round((float(last[2])/float(prior[2])-1)*100,2),source=next(x['url'] for x in m if x['name']==n),note='Use historicalday array; ignore currentday preauction qt embedded in same response.')
def sina(n):return {x[1]:x[2].split(',') for x in re.finditer(r'var hq_str_([^=]+)="([^"]*)";', (B/n).read_text(encoding='utf-8'))}
f=sina('sina_us.txt')['gb_sox'];assert 'Nov 10' in f[25]
sox=dict(price=float(f[1]),change_pct=float(f[2]),market_session='2026-11-10',provider_updated_beijing=f[3],source='https://hq.sinajs.cn/list=gb_sox',instrument='Philadelphia_Semiconductor_Index_not_SOXX_ETF')
c=sina('sina_cross.txt');assets=[]
for code,label,unit in [('hf_CHA50CFD','A50 futures vendor indication','points'),('hf_CL','WTI futures vendor indication','USD_per_barrel'),('hf_GC','Gold futures vendor indication','USD_per_ounce')]:
 f=c[code];assert f[12]=='2026-11-11'
 assets.append(dict(name=label,value=float(f[0]),unit=unit,previous_vendor_settlement=float(f[7]),change_pct=(float(f[0])/float(f[7])-1)*100,quote_time_beijing=f[12]+'T'+f[6]+'+08:00',source='https://hq.sinajs.cn/list='+code,is_current_morning_quote=True,caveat='Vendor indication not independently verified exchange direct. Comparison uses vendor settlement field.'))
for code,label in [('fx_susdcnh','USD/CNH'),('DINIW','Dollar index')]:
 f=c[code];assert f[-1]=='2026-11-11'
 assets.append(dict(name=label,value=float(f[8]),previous_vendor_close=float(f[3]),change_pct=(float(f[8])/float(f[3])-1)*100,quote_time_beijing=f[-1]+'T'+f[0]+'+08:00',source='https://hq.sinajs.cn/list='+code))
y=load(B/'cnbc_yields.txt')['FormattedQuoteResult']['FormattedQuote'][0];assert y['last_time'].startswith('2026-11-10')
assets.append(dict(name='US10Y Treasury yield',value_pct=float(y['last'].rstrip('%')),previous_vendor_close_pct=float(y['previous_day_closing'].rstrip('%')),change_bp=(float(y['last'].rstrip('%'))-float(y['previous_day_closing'].rstrip('%')))*100,quote_time_exchange=y['last_time'],source=next(x['url'] for x in m if x['name']=='cnbc_yields'),provider='CNBC Quote Cache / Tradeweb',caveat='Timed electronic bond quote, not current Beijing09:17 or exact16:00US equity close.'))
turnover=(6739.52+8308.61)*1e8
review=dict(available=True,forecast_file='2026-11-10.json',original_forecast=prev['forecast'],observed={k:dict(open_change_pct=(v['open']/v['previous_close']-1)*100,close_change_pct=v['change_pct'],close_below_open=v['price']<v['open']) for k,v in a.items()},assessment='高开方向兑现，全天收涨但均低于开盘；主情景震荡修复部分兑现，冲高回落风险也兑现。创业板高开约2.44%收涨1.46%，不能称普遍反转。',deviation_reason='盘面表现为反弹持续性不足；市场广度改善但量能仅温和增加，不能精确归因于未经核实的资金流。',numeric_hit_rate=None)
out=dict(prepared_at=datetime.now(timezone.utc).isoformat(),last_completed_us_session='2026-11-10',us_equities=us,sox=sox,a_share_previous_close=a,previous_sh_sz_turnover_yuan=turnover,previous_sh_sz_turnover_source='https://finance.ce.cn/stock/gsgdbd/202611/t20261110_3289989.shtml',previous_sh_sz_turnover_change_vs_prior_day_pct=(turnover/prev['previous_sh_sz_turnover_yuan']-1)*100,cross_assets=assets,previous_forecast_review=review,current_day_auction_quotes_excluded_from_prior_session=True)
(B/'market.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(sox=sox,A_previous=a,turnover=turnover,turnover_change_pct=out['previous_sh_sz_turnover_change_vs_prior_day_pct'],assets=assets,review=review['observed']),ensure_ascii=False,indent=2))
