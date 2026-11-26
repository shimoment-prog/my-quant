import concurrent.futures as cf
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE=Path('/private/tmp/a-share-premarket-2026-11-11')
BASE.mkdir(parents=True,exist_ok=True)
targets=[
 ('tencent_kline_sh','https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000001,day,2026-11-09,2026-11-10,2,qfq'),
 ('tencent_kline_sz','https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz399001,day,2026-11-09,2026-11-10,2,qfq'),
 ('tencent_kline_cyb','https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz399006,day,2026-11-09,2026-11-10,2,qfq'),
 ('tencent_us','https://qt.gtimg.cn/q=usDJI,usIXIC,usINX,usNVDA,usAMD,usMSFT,usMETA,usAMZN,usGOOG,usAVGO,usLITE,usMRVL,usCOHR,usCIEN,usAAOI,usFN,usQCOM,usARM,usCRWV,usIREN'),
 ('tencent_a','https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000300,sh603986,sz300750,sz300502,sz300308,sz000858,sh600519'),
 ('sina_us','https://hq.sinajs.cn/list=gb_sox,gb_dji,gb_ixic,gb_inx,gb_qcom,gb_arm,gb_cohr,gb_iren,gb_aaoi,gb_lite,gb_mrvl,gb_nvda,gb_avgo'),
 ('sina_cross','https://hq.sinajs.cn/list=hf_CHA50CFD,fx_susdcnh,DINIW,hf_GC,hf_CL,hf_OIL'),
 ('cnbc_yields','https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=US10Y&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json'),
]
def run(pair):
 name,url=pair
 result={'name':name,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat()}
 try:
  headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}
  with urlopen(Request(url,headers=headers),timeout=18) as r:data=r.read();result['status']=r.status
  text=data.decode('gb18030' if name.startswith(('tencent','sina')) else 'utf-8',errors='replace')
  (BASE/(name+'.txt')).write_text(text)
  result.update({'ok':True,'bytes':len(data)})
  if name.startswith('tencent'):
   quotes=[]
   for line in text.splitlines():
    if '="' not in line:continue
    code=line.split('=',1)[0].replace('v_','');f=line.split('"')[1].split('~')
    if len(f)<38:continue
    q={'code':code,'name':f[1],'price':f[3],'prev':f[4],'open':f[5],'time':f[30],
       'pct':f[32],'high':f[33],'low':f[34],'amount_field':f[35],'amount_index37':f[37]}
    quotes.append(q)
   result['quotes']=quotes
  if name=='eastmoney_breadth':
   d=json.loads(text);items=(d.get('data') or {}).get('diff') or []
   if isinstance(items,dict):items=list(items.values())
   valid=[i for i in items if isinstance(i.get('f3'),(int,float)) and isinstance(i.get('f2'),(int,float))]
   result['breadth']={'reported_total':(d.get('data') or {}).get('total'),'rows_received':len(items),
    'valid':len(valid),'advancers':sum(i['f3']>0 for i in valid),
    'decliners':sum(i['f3']<0 for i in valid),'flat':sum(i['f3']==0 for i in valid)}
 except Exception as e:result.update({'ok':False,'error':type(e).__name__+': '+str(e)})
 return result
with cf.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(run,targets))
(BASE/'quote_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
for r in results:print(json.dumps(r,ensure_ascii=False))
