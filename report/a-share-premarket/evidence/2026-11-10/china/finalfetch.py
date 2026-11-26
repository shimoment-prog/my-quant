exec(open('/private/tmp/a-share-premarket-2026-11-10/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={};urls={'ce_close':'https://finance.ce.cn/stock/gsgdbd/202611/t20261109_3288584.shtml','mofcom':'https://www.mofcom.gov.cn/','chinanews_search':'https://www.chinanews.com.cn/cj/'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:r=list(ex.map(get,urls.items()))
(b/'finalfetch_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
