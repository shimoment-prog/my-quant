exec(open('/private/tmp/a-share-premarket-2026-11-11/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={'clsclose':'"2026年11月10日" "收评" "上涨"','broad':'"11月10日" "全市场" "飘红"'}
urls={'ce_page1':'https://finance.ce.cn/stock/gsgdbd/index_1.shtml','ce_page2':'https://finance.ce.cn/stock/gsgdbd/index_2.shtml','cls_morning':'https://www.cls.cn/detail/2530870','pbc_report':'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026110510330636555/index.html'}
urls.update({k:'https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=zh-CN&gl=CN&ceid=CN:zh-Hans' for k,q in qs.items()})
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:r=list(ex.map(get,urls.items()))
(b/'details_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
