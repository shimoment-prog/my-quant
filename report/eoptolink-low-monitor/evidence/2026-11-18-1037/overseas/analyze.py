import json,re,datetime,shutil
from pathlib import Path
from zoneinfo import ZoneInfo
p=Path('/private/tmp/eoptolink-nov18-1030-overseas')
b=Path('/Users/richao11/myproject/my-quant/report/overseas-optics-premarket')
pre=json.loads((b/'observations/2026-11-18-0857.json').read_text())
prior=json.loads(Path('/Users/richao11/myproject/my-quant/report/eoptolink-low-monitor/observations/2026-11-17-1434.json').read_text())
man=json.loads((p/'manifest.json').read_text()); mi={x['id']:x for x in man}
tencent={n[2:]:r.split('~') for n,r in re.findall(r'v_([^=]+)="(.*?)";',(p/'us_tencent.raw').read_bytes().decode('gb18030'))}
market={}
for n,r in re.findall(r'var hq_str_([^=]+)="(.*?)";',(p/'us_sina.raw').read_bytes().decode('gb18030')):
 a=r.split(',');s=n[3:].upper();s='.IXIC' if s=='IXIC' else s
 q=dict(symbol=s,name=a[0],regular_close=float(a[1]),regular_change_pct=float(a[2]),regular_session_date='2026-11-17',regular_session_close_at_beijing='2026-11-18T05:00:00+08:00',regular_source_label=a[25],provider_updated_at_beijing=a[3],source='us_sina.raw',currency='USD' if s not in ['SOX','.IXIC'] else None,afterhours=None)
 if s in tencent:
  t=tencent[s];q['tencent_crosscheck']={'regular_close':float(t[3]),'regular_change_pct':float(t[32]),'source_update_exchange':t[30],'source':'us_tencent.raw'}
  assert abs(float(t[3])-q['regular_close'])<0.01 and abs(float(t[32])-q['regular_change_pct'])<0.02
 if a[24]:
  et=datetime.datetime.strptime(a[24].replace(' EST','')+' 2026','%b %d %I:%M%p %Y').replace(tzinfo=ZoneInfo('America/New_York'))
  q['afterhours']={'price':float(a[21]),'change_vs_regular_close_pct':float(a[22]),'time_exchange':et.isoformat(),'time_beijing':et.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),'source_label':a[24],'source':'us_sina.raw','snapshot_not_certified_final':True}
 q['premarket']={'price':None,'time':None,'note':'11月18日常规美股盘前未开始；Robinhood隔夜报价另属独立时段。'}
 market[s]=q
cal=pre['trading_day'].copy();cal['official_calendar_original_checked_at']=cal.pop('checked_at');cal['temporary_closure_indices_refreshed_at']=mi['sse_general']['retrieved_at'];cal['refresh_note']='10:35:43沪深一般公告索引与今晨逐字节相同，可见范围未见全市场临时休市。年度日历及深交所最近休市原文沿用08:48核查。'
comp=[]
for n,old in [('sse_general','/private/tmp/optics-nov18-calendar/sse_general.html'),('szse_general','/private/tmp/optics-nov18-calendar/szse_notice.html'),('mrvl_ir','/private/tmp/optics-nov18-events/mrvl_ir.txt'),('nvda_news','/private/tmp/optics-nov18-events/nvda_news.txt')]:
 old=Path(old)
 if old.exists():comp.append(dict(id=n,same_raw_as_premarket=(p/(n+'.raw')).read_bytes()==old.read_bytes(),premarket_file=str(old),refreshed_file=str(p/(n+'.raw'))))
rows=[]
for f in p.glob('news_*.raw'):rows+=json.loads(f.read_bytes())['result']['data']['feed']['list']
rows=sorted({r['id']:r for r in rows}.values(),key=lambda x:x['create_time'])
matched=json.loads((p/'incremental_news_matched.json').read_text())
for x in matched:
 if x['id']==5221407:x.update(classification='duplicate_of_premarket_verified_supply_commitments',note='3900亿美元采购承诺及基板/封装合作已在今晨SEC/CFO/官方稿核实；转载不是新经营事件，亦非光模块实际订单。')
 elif x['id']==5221437:x.update(classification='new_secondary_management_reassurance',note='管理层客户/员工支持表态；未取得独立量化新订单或实际交付证据。')
 elif x['id']==5221556:x.update(classification='separate_overnight_platform_not_regular_or_premarket',note='Robinhood短暂回吐涨幅属于独立隔夜平台，非正常盘/常规盘前，未取得带时点独立报价，不混入行情表。')
 else:x.update(classification='non_core_or_strategy_context',note='不构成六家海外光通信量化订单、盈利或交付的新证据。')
a=p/'reused_primary';a.mkdir(exist_ok=True)
for origin in ['/private/tmp/optics-nov18-calendar/findings.json','/private/tmp/optics-nov18-events/findings.json','/private/tmp/optics-nov18-regulation/findings.json']:
 origin=Path(origin);shutil.copy2(origin,a/(origin.parent.name+'_'+origin.name))
out=dict(schema_version=1,prepared_at=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),scope='有限增量核查：600条新浪快讯、Marvell IR、NVIDIA新闻、沪深一般公告、腾讯/新浪美股报价。复用今晨已核SEC/公司原文并保留原核查时点。',baseline_intraday_observation='/Users/richao11/myproject/my-quant/report/eoptolink-low-monitor/observations/2026-11-17-1434.json',baseline_intraday_news_cutoff_at=prior['overseas']['news_query_complete_through_retrieval_at'],premarket_research_observation=str(b/'observations/2026-11-18-0857.json'),premarket_research_cutoff_at=pre['data_cutoff_at'],trading_day=cal,us_session=pre['us_session'],last_completed_US_regular_session='2026-11-17',US_regular_close_beijing='2026-11-18T05:00:00+08:00',market=market,market_summary='六家光通信正常盘全涨0.13%至3.65%，五家强于费半+0.34%。盘后08:58—08:59北京末段快照中五家上涨4.60%至7.16%、AAOI跌8.67%；英伟达盘后+4.82%。未认证20:00最后成交。',new_verified_primary_operating_events_since_last_intraday=pre['overseas_events']['new_verified_primary_events'],new_verified_primary_events_since_premarket_cutoff=[],regulation_followup_reused=pre['regulation_followup'],company_event_timing_note='NVDA财报/供应承诺/治理委员会、AAOI融资及商务部回应相对11月17日14:30监测属新增；已在今早盘前报告披露，本次复用而非10:30新披露。',incremental_secondary_context=matched,news_coverage=dict(pages=6,rows=len(rows),earliest_item_at=rows[0]['create_time'],latest_item_at=rows[-1]['create_time'],matches_after_085412=len(matched),retrieved_through=mi['news_1']['retrieved_at']),raw_comparisons=comp,absence_statement='本次可访问IR/新闻索引及快讯未核实08:54后新增六企盈利预警、量化订单取消或客户资本开支削减；有限覆盖不证明所有渠道无消息。',limits=['费半仅新浪指数源，缺独立第二指数核验；SOXX ETF不替代SOX。','连续5/20日及完整美股分时缺失，不由收盘涨跌推断日内路径。','盘后为08:58—08:59末段快照，未认证20:00最后成交；与Robinhood隔夜交易分开。','AAOI最高5.5亿美元ATM是融资能力，不等于已募足或客户撤单。','NVDA1300亿美元±3%下季收入、71%—72%毛利率是展望；季度多一周，不是已实现业绩。','美国远程芯片规则全文、生效日及光模块适用范围未核实，不能写国内光模块已受禁或丢单。','未修改state、历史观察或任何预测。'],source_manifests=man,reused_primary_evidence_directories=['/private/tmp/optics-nov18-events','/private/tmp/optics-nov18-regulation','/private/tmp/optics-nov18-calendar'],reused_local_summaries=[str(x) for x in a.glob('*')])
(p/'findings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'file':str(p/'findings.json'),'prepared_at':out['prepared_at'],'market_rows':len(market),'comparisons':comp},ensure_ascii=False))
