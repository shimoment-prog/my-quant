exec(open('/private/tmp/a-share-premarket-2026-11-09/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={}
urls={'gov_meeting':'https://www.gov.cn/yaowen/liebiao/202611/content_7085401.htm','ce':'https://finance.ce.cn/stock/gsgdbd/','cls':'https://www.cls.cn/','google_close':'https://www.google.com/search?q='+urllib.parse.quote('2026年11月6日 收评 上涨 下跌 成交额 申万'),'google_szse':'https://www.google.com/search?q='+urllib.parse.quote('site:szse.cn 2026年 部分节假日 休市安排'),'google_repurchase':'https://www.google.com/search?q='+urllib.parse.quote('site:csrc.gov.cn 2026年11月6日 回购 护盘')}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:r=list(ex.map(get,urls.items()))
(b/'details_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
