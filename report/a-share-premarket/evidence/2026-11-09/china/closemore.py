exec(open('/private/tmp/a-share-premarket-2026-11-09/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={};urls={'ce_page3':'https://finance.ce.cn/stock/gsgdbd/index_3.shtml','ce_page4':'https://finance.ce.cn/stock/gsgdbd/index_4.shtml','sse_home':'https://www.sse.com.cn/','szse_notice':'https://www.szse.cn/disclosure/notice/general/index.html'}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:r=list(ex.map(get,urls.items()))
(b/'closemore_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
