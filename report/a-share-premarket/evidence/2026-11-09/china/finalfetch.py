exec(open('/private/tmp/a-share-premarket-2026-11-09/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={};urls={'ce_close':'https://finance.ce.cn/stock/gsgdbd/202611/t20261106_3286124.shtml','ce_stable':'https://finance.ce.cn/stock/gsgdbd/202611/t20261109_3287514.shtml','cls_tele':'https://www.cls.cn/telegraph'}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:r=list(ex.map(get,urls.items()))
(b/'finalfetch_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
