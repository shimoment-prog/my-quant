import copy,datetime,hashlib,json,re,shutil
from pathlib import Path
from zoneinfo import ZoneInfo
p=Path('/private/tmp/eoptolink-nov18-1430-overseas')
a=Path('/private/tmp/eoptolink-nov18-1030-overseas')
base_path=Path('/Users/richao11/myproject/my-quant/report/eoptolink-low-monitor/observations/2026-11-18-1037.json')
base=json.loads(base_path.read_text())['overseas']
man=json.loads((p/'manifest.json').read_text());mi={x['id']:x for x in man}
supp=json.loads((p/'supplement_manifest.json').read_text());reportman=json.loads((p/'report_manifest.json').read_text())
# A guessed supplementary Sina URL returned a different report and is excluded from evidence used.
supp=[x for x in supp if x['id']!='sina_short']
cal=copy.deepcopy(base['trading_day'])
cal['temporary_closure_indices_refreshed_at']=mi['sse_general']['retrieved_at']
cal['refresh_note']='14:29:44刷新沪深一般公告；深交所与上午逐字节相同。上交所新列纳斯达克100ETF临时停牌，仅属单基金交易安排，不是沪深全市场休市。年度日历沿用今晨官方核查。'
cal['individual_fund_halt_not_market_closure']={'title':'纳斯达克100交易型开放式指数证券投资基金临时停牌公告','date':'2026-11-18','scope':'single ETF, not market-wide closure'}
rows=[]
for f in p.glob('news_*.raw'):rows+=json.loads(f.read_text())['result']['data']['feed']['list']
rows=sorted({x['id']:x for x in rows}.values(),key=lambda x:x['create_time'])
pat=re.compile('英伟达|Lumentum|Marvell|Coherent|Ciena|Fabrinet|AAOI|光通信|光模块|光电|1.6T|800G|CPO|NPO|数据中心|芯片|博通|微软|亚马逊|谷歌|META|AI基建|资本开支|存储|服务器|电力',re.I)
matched=[]
classification={5222063:('newly_verified_original_short_report_dated_20261117','已核公开原始网页；是11/17做空报告，本次首次核实，非今天14:14才公布。指控未证实，不当违规事实或国内撤单。'),5221921:('secondary_management_comment_not_quantified_order','谨慎评估投资/担保的电话会媒体转述，与已知融资约束背景相关；未取得完整电话会原文，非已证实撤单。'),5221785:('financing_strategy_opinion','阿波罗CEO对AI融资规模和新云信用风险的观点，非实际需求或已实现订单。'),5221957:('analyst_regulatory_scenario','银河国际对东南亚CAPEX潜在影响的研判，不是已实现资本开支削减；美国规则全文生效和产品范围仍缺。'),5221964:('secondary_policy_statement','新加坡协助核查表态，非新增已生效规则或模块禁令。'),5221965:('secondary_policy_statement','新加坡总理表态，不能当作需求或订单实现。'),5221906:('domestic_company_claim_not_foreign_module_order','协创数据自身服务器采购/排产公告的媒体摘录；非新易盛订单或实际交付证明。'),5221976:('domestic_supplier_management_claim','联讯仪器需求和订单表述，非六家海外量化新披露。'),5222010:('domestic_supplier_capacity_outlook','源杰科技需求和产能建设表述；未来形成产能非已交付模块。'),5222030:('industry_price_forecast','TrendForce内存价格预测，非实际成交或光模块采购。')}
for r in rows:
 if r['create_time']>'2026-11-18 10:35:10' and pat.search(r.get('rich_text','')+r.get('title','')):
  c,n=classification.get(r['id'],('non_core_strategy_or_price_target','不构成六家海外光通信新增量化订单、财报或交付证据；资金分类不用于推断机构真实流入。'))
  matched.append({'id':r['id'],'published_at_beijing':r['create_time'],'text':r['rich_text'],'source':r.get('docurl'),'classification':c,'note':n})
(p/'incremental_news_matched.json').write_text(json.dumps(matched,ensure_ascii=False,indent=2)+'\n')
new_event={'id':'MW_NVDA_short_report_20261117_newly_verified_20261118_1431','symbols':['NVDA'],'classification':'primary_disclosure_of_short_position_and_unproven_allegations_not_verified_demand_change','original_publication_date':'2026-11-17','original_exact_publication_time':None,'media_republication_at_beijing':'2026-11-18T14:14:46+08:00','verified_at_beijing':'2026-11-18T14:31:31+08:00','source':'https://muddywatersresearch.com/research/2026/mw-short-nvda/','secondary_source':'https://finance.sina.cn/7x24/2026-11-18/detail-inizcvvf1575656.d.html','facts_about_disclosure':['Muddy Waters publicly states it is short NVIDIA.','It raises questions about whether the Cenly Chen/Cenly Puri photographed with former NVIDIA executive Ajay Puri is the same Cenly Chen formerly employed by SMCI.','It cites an October class action and March prosecution as background; these are not newly effective regulations.','The original webpage explicitly says the class-action allegations are unproven and no government has indicted or criminally accused Cenly Chen.'],'impact':'新增核实的合规/声誉和情绪不确定性；做空方有利益关系，指控不等于已证实违规、收入造假或国内光模块订单取消。','body_limit':'Read public webpage; downloadable PDF requiring terms acknowledgement not downloaded; no independent court docket/company response retrieved.'}
comparisons=[]
for n in ['sse_general','szse_general','mrvl_ir','nvda_news']:
 comparisons.append({'id':n,'same_raw_as_morning':(p/(n+'.raw')).read_bytes()==(a/(n+'.raw')).read_bytes(),'morning_sha256':hashlib.sha256((a/(n+'.raw')).read_bytes()).hexdigest(),'current_sha256':mi[n]['sha256']})
rdir=p/'reused_morning';rdir.mkdir(exist_ok=True)
for name in ['findings.json','manifest.json','us_sina.raw','us_tencent.raw']:
 shutil.copy2(a/name,rdir/name)
shutil.copytree(a/'reused_primary',rdir/'reused_primary',dirs_exist_ok=True)
limits=list(base['limits'])+['下午未重抓六企全部SEC或IR；增量覆盖800条快讯及Marvell/NVIDIA列表，有限覆盖不证明所有渠道无披露。','浑水报告日期11/17，本次新核实；未取得精确原发布时间，不能称14:14新发布或把未证实指控当事实。','美国11月18日常规盘前为北京时间17:00后开始；14:30尚未开始。上午08:58—59盘后快照是旧时段，Robinhood隔夜另属独立平台。']
out={'schema_version':1,'prepared_at':datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'scope':'下午有限增量：800条快讯、Marvell IR、NVIDIA新闻、沪深general与浑水公开原报告；正常美股与盘后沿用上午已核数据。','baseline_observation':str(base_path),'baseline_news_data_cutoff_at':'2026-11-18T10:35:10+08:00','news_query_complete_through_retrieval_at':mi['news_1']['retrieved_at'],'trading_day':cal,'us_session':base['us_session'],'last_completed_US_regular_session':base['last_completed_US_regular_session'],'US_regular_close_beijing':base['US_regular_close_beijing'],'market':copy.deepcopy(base['market']),'market_reused_from':'上午10:35双源核查；正常盘属于11/17，盘后08:58—59北京快照，未认证最终成交。','market_summary':base['market_summary'],'newly_verified_primary_events_since_last_check':[new_event],'new_verified_primary_operating_events_since_last_intraday':[],'reused_primary_events':copy.deepcopy(base['new_verified_primary_operating_events_since_last_intraday']),'regulation_followup_reused':base['regulation_followup_reused'],'company_event_timing_note':'NVDA财报/供应承诺/治理委员会、AAOI融资和商务部回应均已在今晨披露并报告，不包装为下午新经营变化。浑水报告是11/17发布、本次首次原文核实。','incremental_secondary_context':matched,'news_coverage':{'pages':8,'rows':len(rows),'earliest_item_at':rows[0]['create_time'],'latest_item_at':rows[-1]['create_time'],'matches_after_103510':len(matched),'retrieved_through':mi['news_1']['retrieved_at']},'raw_comparisons':comparisons,'absence_statement':'本次有限IR/新闻索引及快讯覆盖未核实上午后六家海外光通信新增量化撤单、盈利预警或客户资本开支实际削减；新增核实浑水做空报告仅作为合规/情绪不确定性。','limits':limits,'sources':man+supp+reportman,'source_manifests':man+supp+reportman,'reused_primary_evidence_directories':base['reused_primary_evidence_directories'],'reused_morning_evidence_directory':str(rdir)}
(p/'findings.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'file':str(p/'findings.json'),'prepared_at':out['prepared_at'],'newly_verified_primary':new_event,'calendar_comparisons':comparisons,'news_coverage':out['news_coverage']},ensure_ascii=False,indent=2))
