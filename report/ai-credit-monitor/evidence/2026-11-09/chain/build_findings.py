import datetime,json
from pathlib import Path
b=Path('/private/tmp/ai-credit-monitor-2026-11-09/chain')
sec=json.loads((b/'submission_manifest.json').read_text())
news=json.loads((b/'news_manifest.json').read_text())
g={r['name']:r['items'] for r in news}
def discovery(group,index,disposition):
 return {**g[group][index],'record_type':'public_RSS_discovery_not_substantive_original_body_verification','disposition':disposition}
lines=[
 discovery('lenders',6,'RSS publication 2026-11-08T13:00:00Z, reported in talks to sell/distribute USD40bn SpaceX AI deal. Original Bloomberg body and Edge article not obtained. Stage limited to headline-reported discussions; not confirmed investor orders, closing, drawdown, failed financing or realized loss. USD40bn is a headline transaction-size claim, not cash funded, current liability or impairment.'),
 discovery('ai_chain',11,'RSS publication 2026-11-08T14:53:00Z, SeekingAlpha relay of FT headline claiming Anthropic USD3.4bn generator deal. Full FT/report body not obtained. Treat as reported procurement-agreement lead; supplier, contract signing date, delivery/payment/funding terms and actual cash payment unverified. Not customer cash receipts or verified completed capex.'),
 discovery('lenders',1,'JPMorgan alarm headline lacks accessible body; no new SEC or realized AI loan loss verified. Research commentary title cannot establish bank stop-lending, covenant trigger or actual losses.'),
 discovery('suppliers',6,'AAOI earnings recap published after cutoff, underlying Nov5 results already observed. No new same-period formal revenue cut.'),
 discovery('suppliers',5,'Marvell higher two-year outlook headline is not a new verified same-period downward revision; do not infer demand or funds received from headline.'),
 discovery('ai_chain',15,'Low-grade secondary NVDA CDS139bp claim without original quote time, currency, rank, contract or matched history. Passed to priority branch for possible context only; not new verified market data.'),
 discovery('ai_chain',18,'Google support for USD19bn Anthropic lease repeats prior Nov4TeraWulf support/Nov6financial context. Not a new actual guarantee payout.'),
 discovery('lenders',0,'Apollo origination volume in weekend headline is not actual AI loan impairment; no new company SEC filing since cutoff. No full WSJ body acquired.')
]
f={
 'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'monitor_date_beijing':'2026-11-09',
 'comparison_cutoff_utc':'2026-11-08T00:37:20.050260+00:00',
 'assessment_suggested':'观察',
 'notification_suggested':'DONT_NOTIFY',
 'material_new_disclosure':False,
 'summary':'No newly verified material supplier, same-project escalation or realized lender-loss event since cutoff. SEC submissions successfully checked for all14 issuers: no filings of any type after cutoff. TeraWulf official release index latest remains Nov6. Newly discovered SpaceX distribution-discussion and Anthropic generator-procurement headlines lack accessible original bodies/primary terms; record as unverified financing/procurement leads, not closed financing, actual capex or realized credit stress. Preserve existing risk assessment, not risk relief.',
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
   'AAOI':'Nov8 news recaps Nov5 earnings; previously documented2027 power/construction delay is not a new cancellation or formal guidance cut.',
   'Marvell_Lumentum':'Stock/acquisition and longer-range-outlook headlines are not issuer same-period formal revenue cuts or verified cancelled orders.',
   'limits':'SEC and targeted public-news checks do not cover all IR/earnings transcripts; absence of verified new cuts cannot prove stable demand.'
 },
 'same_project_escalation_checks':{
   'IREN_Microsoft':{'new_cancelled_order_verified':False,'new_customer_prepayment_refund_verified':False,'new_financing_interruption_verified':False,'finding':'No new SEC filing; new recap headlines do not independently verify escalation of historical delivery timing concerns.'},
   'TeraWulf_Anthropic_Google':{'new_cancelled_order_verified':False,'new_financing_interruption_verified':False,'new_guarantee_payout_verified':False,'finding':'No new SEC filing; press index latest Nov6results then Nov4backstop. Previously anticipated project funding neither verified completed nor failed.'},
   'TeraWulf_Fluidstack_LakeMariner':{'new_cancellation_verified':False,'finding':'No reviewed new update changes historical CB4Q42026/CB5early2027 milestones.'}
 },
 'lender_checks':{
   'issuers':['Apollo','Blackstone','Ares','JPMorgan'],
   'new_AI_specific_loan_impairment_verified':False,
   'new_AI_specific_stop_lending_verified':False,
   'new_actual_guarantee_payment_verified':False,
   'new_actual_default_or_covenant_trigger_verified':False,
   'finding':'No post-cutoff SEC filing. New SpaceX USD40bn secondary deal-distribution discussion title is not evidence of actual failed financing or loan loss. Fund earnings, origination volumes and research alarm titles cannot establish AI-specific realized losses.',
   'limits':'Private-credit loan-level data and full paid WSJ/Bloomberg reporting not obtained; no claim of zero losses in all underlying portfolios.'
 },
 'news_discovery_not_new_verified_event':lines,
 'followup_candidates':[
   {'id':'spacex_20261108_reported_40bn_distribution_discussions_unverified','publication_at_rss':'2026-11-08T13:00:00Z','source':g['lenders'][6]['link'],'evidence_grade':'publisher_RSS_headline_relaying_Bloomberg_only','transaction_stage':'headline_reported_discussions_not_verified_priced_closed_or_drawn','nominal_headline_amount_USD':40000000000,'underlying_event_or_contract_date':None,'company_confirmation':False,'actual_cash_receipt_or_payment_verified':False,'funding_failure_or_realized_loss_verified':False,'assessment_impact':'Insufficient evidence to change observation rating or quantify current financing buffer; obtain original terms and execution stage before counting as event.'},
   {'id':'anthropic_20261108_reported_3_4bn_generators_unverified','publication_at_rss':'2026-11-08T14:53:00Z','source':g['ai_chain'][11]['link'],'evidence_grade':'SeekingAlpha_RSS_headline_relaying_FT_only','transaction_stage':'reported_procurement_deal_not_verified_cash_purchase_or_funded_project','nominal_headline_amount_USD':3400000000,'underlying_event_or_contract_date':None,'supplier':None,'delivery_and_payment_terms':None,'company_confirmation':False,'actual_cash_payment_verified':False,'assessment_impact':'Potential commitment lead only; do not count as new cash capex, verified demand receipts or new credit deterioration/relief.'}
 ],
 'public_IR_index_checks':[
   {'issuer':'TeraWulf','source':'https://investors.terawulf.com/news-events/press-releases','status':'retrieved','latest_release':'Nov6 2026 7:00am EST Q3results; next prior Nov4Googlebackstop','new_post_cutoff_release_found':False},
   {'issuer':'IREN','source':'https://iren.gcs-web.com/news-releases','status':'403_not_bypassed'}
 ],
 'collection_limits':[
   'No full private-credit portfolio loan-level/payment-aging information.',
   'No individual issuer CDS or matched bond quote collected by this branch.',
   'No independently verified new supplier cancellation, refund, actual guarantee payout or AI lender impairment.',
   'Some source body requests restricted/timed out; Google News RSS link pages did not expose original article; no paid-wall bypass.',
   'Google/Bing searches returned challenge/empty result pages, not substantive verification; IAB browser unavailable.',
   'Media publication timestamp does not verify underlying contract date or financing execution stage.',
   'Missing evidence is not risk relief or proof adverse events do not exist.'
 ],
 'files':{'SEC_manifest':'submission_manifest.json','news_manifest':'news_manifest.json','IR_retry_manifest':'ir_retry_manifest.json','source_resolution':'resolve_manifest.json','access_limits':'site_search_manifest.json'}
}
(b/'findings.json').write_text(json.dumps(f,ensure_ascii=False,indent=2))
print(json.dumps({'new_filing_count':f['SEC_coverage']['new_filing_count'],'successful_count':f['SEC_coverage']['successful_count'],'notify':f['notification_suggested'],'followups':len(f['followup_candidates'])},ensure_ascii=False))
