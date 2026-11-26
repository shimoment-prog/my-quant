exec(open('/private/tmp/a-share-premarket-2026-11-11/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={'broad2':'"11月10日" "收评" "4200"','zhang':'张国清 上海 调研 2026 11月10日 site:gov.cn','ai_policy':'"人工智能+自然资源" "2026" "11月10日"'}
urls={'ce_close':'https://finance.ce.cn/stock/gsgdbd/202611/t20261110_3289989.shtml'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans' for k,q in qs.items()})
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:r=list(ex.map(get,urls.items()))
(b/'finalfetch_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
