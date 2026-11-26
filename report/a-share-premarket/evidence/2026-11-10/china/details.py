exec(open('/private/tmp/a-share-premarket-2026-11-10/china/fetch.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
qs={};urls={'ce_page1':'https://finance.ce.cn/stock/gsgdbd/index_1.shtml','ce_page2':'https://finance.ce.cn/stock/gsgdbd/index_2.shtml','cls_morning':'https://www.cls.cn/detail/2529608','cls_tech':'https://www.cls.cn/detail/2529634','csrc_news':'http://www.csrc.gov.cn/csrc/c100028/common_list.shtml','pbc_sfisf':'http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026110313380716818/index.html'}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:r=list(ex.map(get,urls.items()))
(b/'details_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
