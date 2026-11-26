import datetime as dt,json,pathlib,re
from zoneinfo import ZoneInfo
P=pathlib.Path('/tmp/zijin-valuation-20261113/market');TZ=ZoneInfo('Asia/Shanghai')
F=json.loads(pathlib.Path('/Users/richao11/myproject/my-quant/report/zijin-valuation-2026-11-11/analysis.json').read_text())['fundamentals']
qs={}
for sy,body in re.findall(r'v_(\w+)="([^"]*)"',(P/'quotes.raw').read_bytes().decode('gb18030')):
 a=body.split('~');qs[sy]=a
ss={sy:bo.split(',')for sy,bo in re.findall(r'hq_str_(\w+)="([^"]*)"',(P/'sina.raw').read_bytes().decode('gb18030'))}
a=qs['sh601899'];s=ss['sh601899'];h=ss['rt_hk02899'];x=ss['fx_shkdcny']
q=dict(price=float(a[3]),previous_close=float(a[4]),open=float(a[5]),change_pct=float(a[32]),high=float(a[33]),low=float(a[34]),quote_time=dt.datetime.strptime(a[30],'%Y%m%d%H%M%S').replace(tzinfo=TZ).isoformat(),vendor_pe_ttm=float(a[39]),vendor_pe_static=float(a[53]),vendor_pb=float(a[46]),turnover_pct=float(a[38]),sina_crosscheck=dict(price=float(s[3]),quote_time=s[30]+'T'+s[31]+'+08:00'))
assert q['price']==q['sina_crosscheck']['price'] and a[30].startswith('20261113')
q['vwap']=float(s[9])/float(s[8]);q['amount_cny']=float(s[9]);q['volume_shares']=float(s[8])
hquote=dict(price_hkd=float(h[6]),change_pct=float(h[8]),quote_time=h[17].replace('/','-')+'T'+h[18]+'+08:00',source='sina.raw rt_hk02899',tencent_delayed_quote_excluded=dict(price=float(qs['hk02899'][3]),quote_time=qs['hk02899'][30]))
fx=dict(hkd_cny=float(x[1]),quote_time=x[17]+'T'+x[0]+'+08:00',indicative_calculated_not_transaction=True)
shares=F['share_capital']['total_ordinary_shares'];cap=q['price']*shares;ttm=F['ttm']['parent_profit_ttm_yuan'];adj=F['ttm']['deducted_profit_ttm_yuan']
valuation=dict(share_count=shares,share_count_as_of=F['share_capital']['as_of'],profit_ttm_cny=ttm,adjusted_profit_ttm_cny=adj,a_price_equivalent_total_value_cny=cap,a_pe_ttm=cap/ttm,adjusted_pe_ttm=cap/adj,static_pe_fy2025=cap/F['ttm']['fy2025_parent_profit_yuan'],pb_common_equity=q['price']/F['valuation_bases']['bps_common_equity_ex_other_instruments'],h_pe_ttm=hquote['price_hkd']*fx['hkd_cny']*shares/ttm,a_premium_to_h_pct=(q['price']/(hquote['price_hkd']*fx['hkd_cny'])-1)*100,normalized_profit_scenarios_not_guidance=[dict(future_annual_profit_yi=y,pe=cap/(y*1e8))for y in [500,600,750]],current_year_q4_flat_q3_scenario=dict(fy2026_profit_yi=(F['ytd2026q3']['parent_profit_yuan']+F['q3standalone']['parent_profit_yuan'])/1e8,pe=cap/(F['ytd2026q3']['parent_profit_yuan']+F['q3standalone']['parent_profit_yuan'])))
assert abs(valuation['a_pe_ttm']-q['vendor_pe_ttm'])<.02
data=json.loads((P/'daily.raw').read_text())['data']['sh601899'];rows=data.get('qfqday',data.get('day'));cl=[z for z in rows if z[0]<'2026-11-13']
assert cl[-1][0]=='2026-11-12'
ma={str(n):dict(value=sum(float(z[2])for z in cl[-n:])/n,previous_value=sum(float(z[2])for z in cl[-n-1:-1])/n,as_of='2026-11-12',today_excluded=True)for n in [5,10,20,60]}
out=dict(analyzed_at=dt.datetime.now(TZ).isoformat(),a_share_quote=q,h_share_quote=hquote,fx=fx,valuation=valuation,technical=dict(completed_daily_last_date=cl[-1][0],daily_adjustment='qfq; not total return',moving_averages=ma,recent_daily_rows=cl[-12:],opening_context='Intraday snapshot at14:30, not a closing price; completed MAs exclude current day.',conditions=dict(stronger='先收回26.70—26.80昨低与昨收区域，再观察27.5及27.9—28.3均线区；需收盘及回踩确认。',weaker='26.10为截至报价时今日低点，25.90为11月2日历史低点；持续失守且反抽无力则弱势延续。历史位置不是保证支撑。')),limitations=['A PE uses price times all ordinary shares divided by consolidated parent-attributable TTM profit; A/H actual market cap is a different denominator.','Tencent HK quote delayed about15minutes; timestamped Sina HK quote used.','Normalized future annual profit sensitivity is not current-year forecast or guidance.','Intraday last price is not closing price.','No verified numerical future-price probability.'])
(P/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
