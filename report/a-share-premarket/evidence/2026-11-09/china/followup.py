exec(open('/private/tmp/a-share-premarket-2026-11-09/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={};urls={'ce_page1':'https://finance.ce.cn/stock/gsgdbd/index_1.shtml','ce_page2':'https://finance.ce.cn/stock/gsgdbd/index_2.shtml','cls_morning':'https://www.cls.cn/detail/2528400','cls_weekend':'https://www.cls.cn/detail/2528259','cls_search':'https://www.cls.cn/searchPage?keyword='+urllib.parse.quote('11月6日 每日收评')}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(get,urls.items()))
(b/'followup_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
