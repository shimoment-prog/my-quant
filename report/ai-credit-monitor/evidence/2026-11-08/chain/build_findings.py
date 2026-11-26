import datetime,json
from pathlib import Path
b=Path('/private/tmp/ai-credit-monitor-2026-11-08/chain')
sec=json.loads((b/'submission_manifest.json').read_text())
news=json.loads((b/'news_manifest.json').read_text())
def item(group,i):
 x=next(r for r in news if r['name']==group)['items'][i]
 return {**x,'record_type':'discovery_only_not_new_verified_primary_event'}
f={
 'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'monitor_date_beijing':'2026-11-08',
 'comparison_cutoff_utc':'2026-11-07T00:33:27.770774+00:00',
 'assessment_suggested':'观察',
 'notification_suggested':'DONT_NOTIFY',
 'material_new_disclosure':False,
 'summary':'No newly verified material supplier/operating-project/lender event since the prior observation. SEC submissions successfully checked for all 14 issuers; no filings of any type after cutoff. Public TeraWulf and Apollo release indexes show no post-cutoff release. Weekend news discovery mostly repeats earlier earnings, credit pressure or commentary. Preserve prior risk concerns; no new evidence is not risk relief.',
 'new_events':[],
 'SEC_coverage':{
   'issuers_checked':[r['company'] for r in sec],
   'successful_count':sum(r['ok'] for r in sec),
   'failed_count':sum(not r['ok'] for r in sec),
   'new_filing_count':sum(len(r.get('new_filings',[])) for r in sec),
   'latest_quarterly_filings':[{'issuer':r['company'],'source':r['url'],'latest_10Q':r.get('latest10q',[])} for r in sec],
   'absence_of_filing_not_exhaustive_operating_evidence':True
 },
 'supplier_checks':{
   'issuers':['NVIDIA','AMD','Marvell','Lumentum','Coherent','Applied Optoelectronics','Fabrinet','Ciena'],
   'new_formal_same_period_revenue_guidance_cut_verified':False,
   'new_consecutive_independent_same_period_cuts_verified':False,
   'new_revision_count_observed_since_cutoff':0,
   'AAOI':'Nov7 news recaps Nov5 Q3 earnings and Q4 guidance385-420m; no new formal same-period revenue revision. Previously documented2027 power/construction delay is not a new cancellation or formal guidance cut.',
   'Marvell_Lumentum':'Weekend market/stock-and-acquisition valuation headlines are not issuer revenue cuts or cancelled customer orders.',
   'limits':'SEC and targeted public-news checks are not exhaustive IR or all conference-transcript coverage; no new verified disclosure cannot prove demand stability.'
 },
 'same_project_escalation_checks':{
   'IREN_Microsoft':{'new_cancelled_order_verified':False,'new_customer_prepayment_refund_verified':False,'new_financing_interruption_verified':False,'finding':'No new SEC filing. Weekend earnings and Microsoft/neocloud headlines repeat earlier events; no independently verified escalation.'},
   'TeraWulf_Anthropic_Google':{'new_cancelled_order_verified':False,'new_financing_interruption_verified':False,'new_guarantee_payout_verified':False,'finding':'No new SEC filing; company press index latest Nov6 results, prior Nov4 backstop. Previously anticipated project funding remains unconfirmed; neither closing nor failure inferred.'},
   'TeraWulf_Fluidstack_LakeMariner':{'new_cancellation_verified':False,'finding':'No new reviewed update changes previously disclosed CB4 Q42026/CB5 early2027 delivery targets.'}
 },
 'lender_checks':{
   'issuers':['Apollo','Blackstone','Ares','JPMorgan'],
   'new_AI_specific_loan_impairment_verified':False,
   'new_AI_specific_stop_lending_verified':False,
   'new_actual_guarantee_payment_verified':False,
   'new_actual_default_or_covenant_trigger_verified':False,
   'finding':'No post-cutoff SEC filings. Apollo official latest release remains Nov3 Q3 results. Public weekend Blackstone risk commentary and Apollo chip-leasing-scale headlines do not establish realized AI lending losses, failed financing or actual guarantee payments.',
   'limits':'Private-credit loan-level data, complete WSJ paid article and project-level confidential loan terms unavailable. No claim of zero losses across all underlying portfolios.'
 },
 'news_discovery_not_new_verified_event':[
   {**item('lenders',1),'disposition':'WSJ risk-commentary title only; full paid article not obtained. No corresponding new SEC event or primary realized-loss disclosure verified. Do not count as an actual AI loan loss.'},
   {**item('lenders',2),'disposition':'Secondary Apollo chip-leasing scale headline, not evidence of closed funding or losses; no post-cutoff company release found.'},
   {**item('iren',2),'disposition':'IREN prior earnings recap; deduplicated against Nov5 disclosure and Nov6/7 observations.'},
   {**item('suppliers',0),'disposition':'AAOI prior earnings recap; deduplicated against Nov5 disclosure and Nov7 historical baseline.'},
   {**item('ai_chain',0),'disposition':'CoreWeave >16% yield story already monitored by priority-credit branch; repeated story not a new comparable quotation.'},
   {**item('ai_chain',9),'disposition':'ING loan-BWIC secondary repeat; not evidence of actual new sale or realized loss.'}
 ],
 'public_IR_index_checks':[
   {'issuer':'TeraWulf','source':'https://investors.terawulf.com/news-events/press-releases','status':'retrieved','latest_release':'Nov6 2026 7:00am EST Q3results; next prior Nov4Googlebackstop','new_post_cutoff_release_found':False},
   {'issuer':'Apollo','source':'https://ir.apollo.com/news-events/press-releases','status':'retrieved','latest_release':'Nov3 2026 6:30am EST Q3results','new_post_cutoff_release_found':False},
   {'issuer':'IREN','source':'https://iren.gcs-web.com/news-releases','status':'403_not_bypassed'},
   {'issuer':'Blackstone','source':'https://www.blackstone.com/news/press/','status':'403_not_bypassed'},
   {'issuer':'Ares','source':'https://ir.ares.com/news-market-data/press-releases','status':'retrieved_uninformative_shell_no_release_content'}
 ],
 'collection_limits':[
   'No full private-credit portfolio loan-level or payment-aging information.',
   'No individual issuer CDS or matched secondary bond quotation collection in this branch.',
   'No independently verified new supplier or end-customer cancellation, refund or actual guarantee payout.',
   'Publication timestamp of a recap does not make underlying historical financials new.',
   'Missing evidence is not risk relief or proof that adverse events do not exist.'
 ],
 'files':{'SEC_manifest':'submission_manifest.json','news_manifest':'news_manifest.json','IR_manifest':'ir_manifest.json','IR_retry_manifest':'ir_retry_manifest.json'}
}
(b/'findings.json').write_text(json.dumps(f,ensure_ascii=False,indent=2))
print(json.dumps({'new_filing_count':f['SEC_coverage']['new_filing_count'],'successful_count':f['SEC_coverage']['successful_count'],'notification':f['notification_suggested'],'path':str(b/'findings.json')},ensure_ascii=False))
