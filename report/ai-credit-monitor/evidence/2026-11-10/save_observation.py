import copy
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor')
TMP = Path('/private/tmp/ai-credit-monitor-2026-11-10')
EVIDENCE = ROOT / 'evidence/2026-11-10'
read = lambda path: json.loads(path.read_text())
before = read(TMP / 'state.before.json')
assert read(ROOT / 'state.json') == before, 'Concurrent state modification; merge required.'
previous = read(ROOT / before['last_observation_file'])
parts = {name: read(EVIDENCE / name / 'findings.json') for name in ['priority', 'bigtech', 'chain']}
shutil.copytree(TMP / 'market', EVIDENCE / 'market', dirs_exist_ok=True)
proxies = read(EVIDENCE / 'market/proxies.json')
now = datetime.now(timezone.utc).isoformat()

sources = []
seen_urls = set()
sec_companies = []
for group in parts:
    for path in sorted((EVIDENCE / group).glob('*_submissions.json')):
        data = read(path)
        cik = str(data['cik']).zfill(10)
        issuer = data.get('name', path.stem)
        rec = data['filings']['recent']
        new = []
        for i, accepted in enumerate(rec['acceptanceDateTime']):
            timestamp = datetime.fromisoformat(accepted.replace('Z', '+00:00'))
            if timestamp > datetime.fromisoformat(before['last_run_at']):
                new.append({key: rec[key][i] for key in ['form', 'accessionNumber', 'primaryDocument', 'acceptanceDateTime']})
        sec_companies.append({'issuer': issuer, 'new_filings_since_prior_cutoff': new[:12], 'new_filings_count': len(new), 'all_incremental_filings_available_in_archived_inventory': True,
                              'archived': str(path.relative_to(ROOT))})
        url = 'https://data.sec.gov/submissions/CIK' + cik + '.json'
        if url not in seen_urls:
            sources.append({'id': group + '_' + path.stem, 'url': url,
                            'type': 'primary_SEC_incremental_filing_inventory',
                            'publication_at': None, 'market_time': None,
                            'archived': str(path.relative_to(ROOT))})
            seen_urls.add(url)
for p in proxies:
    sources.append({'id': p['source_id'], 'url': p['source'], 'data_url': p['data_url'],
                    'type': p['evidence_type'], 'publication_at': None,
                    'market_time': p['observation_date'], 'retrieved_at': p['retrieved_at'],
                    'archived': p['archived_csv']})

assert len(sec_companies) >= 21, 'Incomplete expected issuer coverage.'
# New filings must be classified in each group's reviewed findings before save.
for name, part in parts.items():
    decision = part.get('recommendation', part.get('notification_suggested', part.get('notification_recommendation', part.get('recommended_notification'))))
    assert decision in ['DONT_NOTIFY', 'no_alert_from_this_subtask_alone'], (name, decision, 'Material evidence requires explicit review before silent save.')
signals = []
notes = {
    'real_demand_collections_and_cashflow': '未核实新增正式资本开支或供应商收入指引下修；产品发布、历史财报和工程延期不代替新增回款，保留原披露日期。',
    'credit_funding_and_liquidity': '保留此前局部信用定价压力判断；无新可比个体CDS及现金债券报价，FRED最新仍为11月5日，不视为11月9日行情或风险缓解。',
    'realized_losses_and_cross_entity_propagation': '未核实新增重大融资中断、项目撤单、预付款退还、契约触发、AI专属贷款损失或实际担保赔付；融资推介和媒体评论按证据等级单列。'
}
for old in previous['signals']:
    s = copy.deepcopy(old)
    s.update({'change_since_previous_run': '无已核实的重要新增变化，沿用先前判断；缺失数据不代表风险缓解。',
              'historical_evidence_reference': before['last_observation_file'] + '#signals',
              'latest_review_notes': notes[s['id']]})
    signals.append(s)

focused = copy.deepcopy(previous['focused_checks'])
for item in focused.values():
    item.update({'reviewed_at': now, 'new_material_change_verified': False})
focused['customer_capex_cuts'].update({'new_formal_cut_records': [], 'historical_baseline_unchanged': True,
                                      'new_disclosure_status': 'No new formal company capex guidance revision verified; media views, allocation changes and old project support excluded.'})
focused['supplier_consecutive_revenue_guidance_cuts'].update({
    'new_comparable_revision_count_observed': 0,
    'revision_count_window': {'start': before['last_run_at'], 'end': now},
    'scope_and_limit': {'current_findings': 'evidence/2026-11-10/chain/findings.json',
                        'previous_baseline': before['last_observation_file'] + '#focused_checks',
                        'absence_not_proof_of_stable_demand': True}})
focused['delay_to_cancellation_or_funding_interruption'].update({
    'new_escalation_records': [],
    'project_review_reference': 'evidence/2026-11-10/chain/findings.json',
    'Microsoft_Oracle': 'No new company-confirmed amount, term, cancellation, supplier guidance or formal capex change verified; retain original evidence classification.'})

summary = '本次核查未取得足以改变总体判断的重要新增证据，维持观察并保留此前局部信用压力。FRED新增11月6日整体信用代理，投资级持平、高收益收窄6bp，不能据此确认AI企业风险缓解；拟融资、产品发布和项目诉讼线索按阶段及缺失单列。'
obs = {
    'schema_version': 3, 'date': '2026-11-10', 'automation_id': 'ai',
    'triggered_at': '2026-11-10T00:28:55.472Z', 'run_at': now, 'timezone': 'Asia/Shanghai',
    'baseline': False, 'comparison_to_previous_observation': before['last_observation_file'],
    'assessment': before['assessment'], 'summary': summary,
    'market_session': {'local_day': 'Tuesday', 'US_day_since_prior_run': 'Monday',
                       'new_normal_US_trading_session_since_prior_run': True,
                       'last_normal_session_date': '2026-11-09',
                       'latest_FRED_market_date': '2026-11-06',
                       'lagging_proxies_not_marked_as_live': True},
    'signals': signals, 'new_events': [],
    'market_proxies': proxies,
    'cashflow_definition': previous['cashflow_definition'],
    'historical_financial_baseline_reference': {
        'file': before['supplemental_financial_baseline_file'], 'is_new_release': False,
        'latest_additional_report': before['latest_additional_financial_report'],
        'quarterly_financials_updated_without_new_disclosure': False},
    'focused_checks': focused,
    'financing_stage_review': copy.deepcopy(previous['financing_stage_review']),
    'historical_financing_followups': copy.deepcopy(before.get('historical_financing_followups', [])),
    'weekly_review': {'due_today': False, 'last_completed_date': before['last_weekly_review_date'],
                      'reference': before['last_weekly_review_reference']},
    'source_coverage': {
        'status': 'success_with_existing_IR_and_private_market_information_gaps',
        'incremental_window': {'start': before['last_run_at'], 'end': now},
        'subtask_findings': {k: 'evidence/2026-11-10/' + k + '/findings.json' for k in parts},
        'SEC_checks': sec_companies,
        'market_manifest': 'evidence/2026-11-10/market/manifest.json',
        'incremental_news_items': 'evidence/2026-11-10/market/incremental_news_items.json',
        'fresh_market_download_has_new_observation': any(p['comparison_to_previous_monitor_run']['new_market_observation'] for p in proxies),
        'no_new_public_evidence_is_not_proof_of_absent_risk': True},
    'missing_data': copy.deepcopy(previous['missing_data']),
    'unverified_discovery_and_deduplication': {'details': [
        'evidence/2026-11-10/priority/findings.json',
        'evidence/2026-11-10/bigtech/findings.json',
        'evidence/2026-11-10/chain/findings.json'],
        'rules': 'Preserve source dates and evidence levels. Media reports about discussions, offering distribution, equipment procurement, or contract review do not establish completed funding, lost orders or lender losses.',
        'current_unverified_leads_and_stage_review': {k: 'evidence/2026-11-10/' + k + '/findings.json' for k in parts}},
    'comparability': copy.deepcopy(previous['comparability']),
    'next_confirmation_conditions': copy.deepcopy(previous['next_confirmation_conditions']),
    'sources': sources,
    'notification': {'decision': 'DONT_NOTIFY', 'prepared_at': now,
                      'reason': 'No material verified change since last actual notification; new media commentary/discovery and previously reported pending events do not establish a changed risk judgment.',
                      'overall_assessment_changed': False, 'material_evidence_changed': False,
                      'last_actual_notification_at': before['last_notified_at']},
    'interpretation_limits': copy.deepcopy(previous['interpretation_limits']),
    'raw_evidence_directory': 'evidence/2026-11-10'
}
for row in obs['historical_financing_followups']:
    row['last_checked_at'] = now

state = copy.deepcopy(before)
state.update({'last_run_at': now, 'last_observation_file': 'observations/2026-11-10.json',
              'last_run_summary': summary, 'last_notification_decision': 'DONT_NOTIFY',
              'consecutive_overall_collection_failures': 0, 'last_fred_collection_status': 'success',
              'latest_market_proxy_date': max(p['observation_date'] for p in proxies)})
for key in ['pending_settlement_checks', 'pending_loan_sale_checks', 'historical_financing_followups']:
    for item in state.get(key, []):
        item['last_checked_at'] = now
for rows in [obs['historical_financing_followups'], state.get('historical_financing_followups', [])]:
    for item in rows:
        if item.get('issuer') == 'OpenAI':
            item.update({'stage': 'media_reported_initial_close_and_wired_asof_Nov6_entire_round_not_closed',
                         'cash_receipt_media_reported': True,
                         'company_confirmation_or_actual_cash_receipt_verified': False,
                         'cash_receipt_independently_verified': False,
                         'evidence_enrichment_publication_at': '2026-11-09T17:38:29.753Z',
                         'source': 'https://www.latimes.com/business/story/2026-11-09/openai-closes-latest-funding-round-at-1-25-trillion-valuation',
                         'evidence_grade': 'reliable_media_Bloomberg_anonymous_sources_not_company_confirmation',
                         'same_underlying_event_as_prior_run': True,
                         'followup': 'First tranche reportedly wired by Nov6 according to anonymous-source media; verify company confirmation, receipts, final round size and direct obligations. Whole round remains open.'})
obs['financing_stage_review']['Apollo_general_corporate_USD600m'] = parts['chain']['events'][0]
obs['new_nonmaterial_context_records'] = [
    {'id': 'apollo-20261109-junior-subordinated-notes-priced', 'findings_reference': 'evidence/2026-11-10/chain/findings.json#events', 'stage': 'priced_not_settled_expected_2026-11-13', 'AI_risk_assessment_changed': False},
    {'id': 'google_20261109_tpu8tx_8imax_product', 'findings_reference': 'evidence/2026-11-10/bigtech/findings.json#new_primary_context', 'cashflow_or_credit_change_verified': False},
    {'id': 'openai_20261106_reported_partial_round_historical_context', 'record_type': 'same_event_evidence_enrichment', 'findings_reference': 'evidence/2026-11-10/priority/findings.json', 'no_new_actual_event_date_assumed': True}
]
obs['new_events'] = [parts['chain']['events'][0]]
obs['sources'].extend([
    {'id': 'apollo_general_corporate_notes_pricing', 'url': 'https://ir.apollo.com/news-events/press-releases/detail/659/apollo-prices-offering-of-fixed-rate-resettable-junior', 'publication_at': '2026-11-09T22:00:00Z', 'market_time': None, 'type': 'primary_company_financing_pricing_not_settlement', 'archived': 'evidence/2026-11-10/chain/apollo_new_notes_ir.txt'},
    {'id': 'coreweave_new_article_quote_time_incomplete', 'url': 'https://www.cnbc.com/2026/11/09/coreweave-debt-credit-risk-neoclouds.html', 'publication_at': '2026-11-09T12:00:01Z', 'market_time': None, 'type': 'reliable_media_undated_market_quotes_not_comparable_trend', 'archived': 'evidence/2026-11-10/priority/coreweave_cnbc.txt'},
    {'id': 'openai_initial_close_media_enrichment', 'url': 'https://www.latimes.com/business/story/2026-11-09/openai-closes-latest-funding-round-at-1-25-trillion-valuation', 'publication_at': '2026-11-09T17:38:29.753Z', 'market_time': '2026-11-06_reported_initial_tranche', 'type': 'reliable_media_relay_Bloomberg_anonymous_sources', 'archived': 'evidence/2026-11-10/priority/latimes.txt'}
])
obs['missing_data'].extend([
    'CoreWeave Nov9 article reports2031bond yield>16%and5yCDS>1240bp without underlying market dates/full metadata; cannot compare to Nov6article2032bond or infer current spread trend.',
    'KED Korea Anthropic project headline body/contract stage unavailable; Alphabet Asia bond considering-stage terms and Louisiana case/court/workstop status not verified.'
])
obs['next_confirmation_conditions'].extend([
    'CoreWeave upcoming Nov10US results: new actual collections/OCF/cashPP&E, liquidity, debt service, capex and deliveries; do not fill in before official release.',
    'Obtain Korea Anthropic project original body/party confirmation; verify signed-contract status before classifying cancellation or financing interruption. Check whether Louisiana litigation obtains an actual injunction or changed project milestones.',
    'ApolloUSD600m expectedNov13closing and AlphabetreportedAsiaplanning: verify actual stages, without treating general corporate financing as proof AI credit stress resolved.'
])
state['seen_event_ids'] = sorted(set(state['seen_event_ids'] + ['apollo-20261109-junior-subordinated-notes-priced']))
state['seen_evidence_ids'] = sorted(set(state.get('seen_evidence_ids', []) + ['google_20261109_tpu8tx_8imax_product', 'openai_20261109_initial_close_media_enrichment', 'coreweave_20261109_media_context_incomplete_quote_time']))
state['pending_other_corporate_financing_checks'] = state.get('pending_other_corporate_financing_checks', []) + [
    {'event_id': 'apollo-20261109-junior-subordinated-notes-priced', 'issuer': 'Apollo', 'currency': 'USD', 'principal': 600000000, 'expected_settlement_date': '2026-11-13', 'stage': 'priced_not_verified_settled_not_due_yet', 'last_checked_at': now, 'AI_specific_funding_or_loss': False}
]
dest = ROOT / 'observations/2026-11-10.json'
if dest.exists():
    existing = read(dest)
    assert not existing.get('notification', {}).get('material_evidence_changed'), 'Same-day material evidence needs explicit merge.'
    obs['same_day_previous_runs'] = existing.get('same_day_previous_runs', []) + [existing]
    obs['new_events'] = existing.get('new_events', [])

for source in sources:
    assert (ROOT / source['archived']).is_file(), source
assert state['last_notified_at'] == before['last_notified_at']
assert state['monitoring_framework'] == before['monitoring_framework']
assert state['completed_financing_checks'] == before['completed_financing_checks']
assert [x['assessment'] for x in signals] == [x['assessment'] for x in previous['signals']]
shutil.copy2(TMP / 'state.before.json', EVIDENCE / 'state.before.json')
shutil.copy2(TMP / 'save_observation.py', EVIDENCE / 'save_observation.py')
for path, data in [(dest, obs), (ROOT / 'state.json', state)]:
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)
for day in ['03', '04', '05', '06', '07', '08', '09']:
    assert (ROOT / ('observations/2026-11-' + day + '.json')).exists()
assert read(dest)['notification']['decision'] == 'DONT_NOTIFY'
assert read(ROOT / 'state.json')['last_notified_at'] == before['last_notified_at']
print(json.dumps({'saved': str(dest), 'assessment': obs['assessment'], 'decision': 'DONT_NOTIFY',
                  'SEC_issuers_checked': len(sec_companies), 'history_preserved': True,
                  'last_actual_notification_preserved': True}, ensure_ascii=False))
