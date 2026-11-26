exec(open('/private/tmp/a-share-premarket-2026-11-10/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={'breadth':'"11月9日" "2200" "3000" A股 收评','clsclose':'"11月9日" "三大指数冲高回落"'}
urls={'mofcom_entity':'https://www.mofcom.gov.cn/xwfb/xwfyrth/art/2026/art_137cb86f6deb442c963c906c2ca97e79.html','mofcom_export':'https://www.mofcom.gov.cn/xwfb/xwfyrth/art/2026/art_5baeb69ccc0f44cb83dea8ac587dd327.html','mofcom_hanwha':'https://www.mofcom.gov.cn/zwgk/zcfb/art/2026/art_41f0892910554f57af175883b35ca360.html'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans' for k,q in qs.items()})
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(get,urls.items()))
(b/'policy_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
