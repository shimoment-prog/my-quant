import urllib.request,json,concurrent.futures,datetime,pathlib
p=pathlib.Path('/private/tmp/ai-credit-monitor-2026-11-10/bigtech');cs={'alphabet':1652044,'meta':1326801,'microsoft':789019,'amazon':1018724,'broadcom':1730168};cut='2026-11-09T00:35:19'
def f(it):
 n,c=it;u=f'https://data.sec.gov/submissions/CIK{c:010d}.json';t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research monitor contact research@example.com'}),timeout=25).read();(p/f'{n}_submissions.json').write_bytes(raw);j=json.loads(raw);z=j['filings']['recent'];rows=[{k:z[k][i] for k in ['accessionNumber','form','filingDate','acceptanceDateTime','primaryDocument']} for i in range(len(z['form'])) if z['acceptanceDateTime'][i]>cut];return {'company':n,'url':u,'retrieved_at':t,'ok':True,'all_new':rows,'new_relevant':[r for r in rows if r['form'] in ['8-K','10-Q','10-K','424B2','424B5','FWP','6-K']],'latest10q':[{k:z[k][i] for k in ['accessionNumber','filingDate','primaryDocument']} for i in range(len(z['form'])) if z['form'][i]=='10-Q'][:1]}
 except Exception as e:return {'company':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,cs.items()));(p/'submission_summary.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
