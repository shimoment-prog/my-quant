import pathlib,json,datetime,hashlib,re,html
B=pathlib.Path('/private/tmp/optics-nov18-events');TZ=datetime.timezone(datetime.timedelta(hours=8));now=datetime.datetime.now(TZ).isoformat()
read=lambda p:json.loads(pathlib.Path(p).read_text())
filings=read(B/'filings.json');state=read('/Users/richao11/myproject/my-quant/report/overseas-optics-premarket/state.json');seen={x['id']for x in state['seen_events']}
man=[]
for n in ['manifest.json','primary_manifest.json','cfo_manifest.json','incremental_manifest.json']:man+=read(B/n)
news={}
for p in B.glob('news_[0-9]*.txt'):
 try:rr=read(p)['result']['data']['feed']['list']
 except Exception:continue
 for r in rr:
  text=html.unescape(re.sub('<[^>]*>',' ',r.get('rich_text','')or r.get('content','')))
  news[str(r.get('id'))]={'time':r.get('create_time'),'text':text,'id':r.get('id'),'source':r.get('docurl')or r.get('url')}
rows=sorted(news.values(),key=lambda x:x['time']);increment=[r for r in rows if r['time']>'2026-11-17 09:43:39']
(B/'news_all_dedup.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
primary=[{
'id':'NVDA_2027Q3_earnings_20261117','symbols':['NVDA'],'classification':'new_primary_earnings_and_forward_guidance',
'sources':['https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2027','https://www.sec.gov/Archives/edgar/data/1045810/000104581026000088/q3fy27pr.htm','https://www.sec.gov/Archives/edgar/data/1045810/000104581026000088/q3fy27cfocommentary.htm'],
'accepted_at_utc':'2026-11-17T21:20:51Z','accepted_at_beijing':'2026-11-18T05:20:51+08:00','official_publication_date':'2026-11-17','reporting_period':'Third quarter fiscal2027 endedOctober25,2026',
'facts':['Actualrevenue$115.8bn,+103%YoY,+20%QoQ;DataCenter$107.6bn,+110%YoY,+21%QoQ.','ActualGAAP/nonGAAPgrossmargin74.8%/74.9%;GAAP/nonGAAPEPS$2.70/$2.68.','ManagementQ4FY27revenueoutlook$130.0bnplusorminus3%($126.1-133.9bn);Q4hasoneadditionalweek;assumesnoDataCentercomputeChinaRevenue.','ManagementexpectsGAAPandnonGAAPgrossmarginbothwithin71.0%-72.0%range,lowerthanQ3actuals.','Actualoperatingcashflow$48.3bn;accountsreceivable$81.0bn;DSO64daysvs60dayspreviousquarter,citingRubinshipmentlinearityandextendedtermsonlargeagreementswithcertaininvestmentgradecustomers.','Supplycommitments$390bnvs$279bn,primarilymultiyearmemoryprocurement;notactualcashpaidandnotopticalmoduleorderamount.','Cloudserviceagreementsanduncommenceddatacenterleases$102bnvs$74bn;additionalneocloudcommitmentsupto$32bnconditionalonfinancing,operationaldeploymentandacceptance;maybereducedoreliminatedifconditionsnotmet.','Maximumgrossguaranteeexposure$118bn,including$105bnSB Energycredit-supportguarantees;phasebyphaseeffectiveness,todatenopaymentsundertheseGuarantees.'],
'impact':'RealizedearningsandforwardrevenueoutlookcounterabruptAIdemandcollapse;lowerfuturegrossmargin,slowerreceivableturnoverandfinancing/executioncontingencieslimitconfidence. Notquantifieddomesticopticalorders.',
'correction_and_dedup':['$150bnadditionalbuybackwasapprovedSeptember2026,notnewlyapprovedthismorning;newdisclosureofpriorapprovaland$227.3bnremainingauthorizationdoesnotmeanalreadyexecutedbuybacks.','SomeSina07:06summarygiveswrong$127.4-132.6bnrange;useprimary$130bn±3%($126.1-133.9bn).','FY28growth75%andindustrybacklog$2.5tnarecallmediaquotesnotverifiedintheobtainedSECpressrelease/CFOtext;retainasattributedoutlookifused.']
},{
'id':'AAOI_ATM_550m_20261117','symbols':['AAOI'],'classification':'new_primary_equity_financing_capacity_not_earnings_or_cancelled_orders',
'sources':['https://www.sec.gov/Archives/edgar/data/1158114/000110465926129055/tm2629531d2_8k.htm','https://www.sec.gov/Archives/edgar/data/1158114/000110465926129051/tm2629531-1_424b5.htm'],
'event_date':'2026-11-17','prospectus_accepted_at_utc':'2026-11-17T21:06:29Z','prospectus_accepted_at_beijing':'2026-11-18T05:06:29+08:00','eightK_accepted_at_beijing':'2026-11-18T05:09:50+08:00','reporting_period':'FinancingagreementandprospectusdatedNovember17,2026;notquarterlyearnings',
'facts':['EnteredEquityDistributionAgreementwithRaymondJamesandNeedham;mayissueandsellupto$550mcommonstockfromtimetotimeasanATMoffering.','Noobligationtosellanyshares;offeringmaybe suspended. Agentscompensationupto2%grosssalesprice.','Intendeduseofnetproceedsifany:generalcorporatepurposesincludingdebtrepayment,workingcapital,capitalexpendituresandacquisitions.','90,771,506commonsharesoutstandingatNov16perprospectus;actualsharesandproceedsdependonfuturemarketpricesandsales.'],
'impact':'Potentialdilutionandfinancingsupplypressureisaseparateidiosyncraticrisk;thefilingdoesnotestablish$550malreadyraised,norcustomerordercancellations. Do not explain all peers by AAOI afterhours decline.'
},{
'id':'NVDA_supply_chain_capacity_commitments_20261117','symbols':['NVDA'],'classification':'new_official_supplier_capacity_plans_not_current_output',
'source':'https://nvidianews.nvidia.com/news/nvidia-expands-commitments-with-supply-chain-partners-to-support-ai-infrastructure-buildout','official_publication_date':'2026-11-17','exact_publication_time_utc':None,'reporting_period':'SupplychaincapacityannouncementNovember17,2026',
'facts':['New/expandedagreementsacrossKinsus,SamsungElectroMechanics,Amkor,SPIL,TSMC,FoxconncoverABFsubstrates,advancedpackagingandmanufacturing.','KinsusNVIDIA-dedicatedABFcapacityplannedover3.5xcurrentYouthcampuslevels;productionexpectedH22027,additionalcapacitytargetQ32028.','VeraRubinNVL72andVeraCPUsbeganvolumeshipmentsinQ3(companyclaim).'],
'impact':'Supportscontinuedmanufacturinginvestmentbutmultiyearcapacityplanisnotcurrentrealizedoutputoropticalmoduleorder. EarlierAmkorJuly/Octoberagreementsincludedasbackground.'
},{
'id':'NVDA_export_security_committee_20261117','symbols':['NVDA'],'classification':'new_official_board_governance_not_new_export_rule',
'source':'https://nvidianews.nvidia.com/news/nvidia-board-of-directors-establishes-national-security-and-export-control-oversight-committee','official_publication_date':'2026-11-17','exact_publication_time_utc':None,'reporting_period':'BoardannouncementNovember17,2026',
'facts':['BoardestablishedstandingNationalSecurityandExportControlOversightCommitteechairedbySuzanneNoraJohnsonwithStephenNealandJohnDabiri.','NationalSecurityandGlobalTradeComplianceTeamsreporttoCommitteeandinterimCEO;retainsindependentoutsideexperts.'],
'impact':'Verifiedgovernancecomplianceaction;neithernewgovernmentexportrestrictionnorconfirmedcustomercancellation.'
}]
secondary=[r for r in increment if re.search('限制远程获取|仍在评估新出口管制|2028财年营收|行业订单积压|融资渠道或|数据中心的计划|芯片从出厂',r['text'])]
for x in secondary:x['classification']='attributed_media_or_management_call_quote_not_independently_verified_primary_in_this_run'
non=[]
for f in filings:
 for r in f['new_filings']:
  if r['form']not in['8-K','424B5']:
   non.append({'symbol':f['symbol'],**r,'classification':'ownership_filing_not_company_earnings_or_customer_orders'})
additions=[]
for x in primary:
 if x['id']not in seen:additions.append({k:v for k,v in x.items()if k in['id','symbols','classification','source','sources','accepted_at_beijing','official_publication_date','event_date']})
for f in filings:
 for r in f['new_filings']:
  i='SEC_'+r['accessionNumber']
  if i not in seen:additions.append({'id':i,'symbol':f['symbol'],'classification':'new_filing_index_item_form_'+r['form'],'filing_date':r['filingDate'],'accepted_at_utc':r['acceptanceDateTime']})
findings={'schema_version':1,'prepared_at':now,'previous_report_cutoff_at':'2026-11-17T09:43:39+08:00','latest_source_retrieval_at':max(x.get('retrieved_at',x.get('started_at',''))for x in man),
'scope':'22pagespublicSinafeed+SECsubmissionindicesforsixoptics,NVDA,AVGO,NBIS;accessibleMarvell/AAOIIR,NVIDIAnews;primaryNVDAearnings,CFOcommentaryandAAOIATMfilings;nochangesoutside/tmp.',
'new_verified_primary_events':primary,'new_non_demand_filings':non,'secondary_unconfirmed_context':secondary,'SEC_index_checks':filings,'seen_events_additions':additions,
'news_coverage':{'pages':22,'unique_ids':len(rows),'earliest':rows[0]['time'],'latest':rows[-1]['time'],'relative_to_prior_cutoff_matched':len(increment),'full_interval_overlaps_baseline':rows[0]['time']<'2026-11-17 09:43:39'},
'deduplication':{'already_reported_not_new':['LambdaNov16CPOdeployment','MRVLNov16Penguinmemory/photoniccooperation','NVDA_Nov12_CEOtransition','NBIS_Nov12deliverydelay','Nov17afternoonPimcoNov10spreadstrategyview','13FSeptember30holdings'],'new_8k_and_press_release_same_event':True,'AAOI8k_and424B5_same_financing':True},
'absence_statement':'BesidesnewAAOIATMfinancing,noverifiednewquarterlyearnings/revenueguidancecutorquantifiedcustomercancellationinthereviewedsixopticpeerindicesandaccessibleIR. No new LITE/MRVLmergertermchangeverified;financingandmergerpricingmustnotbeassumedasdemandloss.',
'limits':['LITE/CIENIRHTTP429,FN/AVGOIR403;Coherentdynamicpresslistlimited.','BISpress-releaseindexrequest404;newremoteadvancedchipaccessmeasuresaremedia-attributedwithoutverifiedruletext/effectivedate/scope,donotpromotetonewlyeffectiveopticalexportban.','CallquotesonFY28growth75%,backlog2.5tn,newexportimpactareattributedmedialines,notindependentlyretrievedfullcalltranscript.','NVDA10-QnotyetfiledperCFOcommentary;currentprimaryinformationfrom8-Kexhibitsandsupplementalfinancialdisclosure.','No verified module-order mapping to Eoptolink/InnoLight;sharepricechangesarenotorderproof.'],
'source_manifests':man,'candidate_report_text':'新增：英伟达11/17盘后披露截至10/25的FY27Q3收入1158亿美元、数据中心1076亿美元，Q4营收指引1300亿美元±3%，但毛利指引71%—72%低于Q3约74.9%；均区分实际与展望。AAOI新设最高5.5亿美元ATM股权发行，可能有融资稀释压力，尚非全额募资或撤单。供应承诺3900亿美元主要为多年存储采购，不等于已付现金或国内光模块订单；担保最大敞口1180亿美元为有条件风险。'}
(B/'findings.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2));print(json.dumps({'prepared_at':now,'primary_event_count':len(primary),'seen_event_additions':len(additions),'news_coverage':findings['news_coverage'],'latest_source_retrieval_at':findings['latest_source_retrieval_at']},ensure_ascii=False,indent=2))
