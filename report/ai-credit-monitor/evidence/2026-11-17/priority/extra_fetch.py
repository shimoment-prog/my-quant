exec(open(__file__.replace('extra_fetch.py','fetch.py')).read().split('m=list(concurrent')[0])
urls={
'hsbc_search':'https://news.google.com/rss/search?q='+urllib.parse.quote('HSBC "300 million" "data center" when:3d')+'&hl=en-US&gl=US&ceid=US:en',
'hsbc_search_alt':'https://news.google.com/rss/search?q='+urllib.parse.quote('HSBC "troubled" "loan" "November" "2026"')+'&hl=en-US&gl=US&ceid=US:en',
'hsbc_investing_search':'https://ca.investing.com/search/?q=HSBC%20offloads',
'breit_amazon':'https://www.businesstimes.com.sg/companies-markets/blackstone-reit-buys-amazon-data-centres-us5-billion-deal',
'openai_semafor':'https://www.semafor.com/article/11/16/2026/openai-cfo-says-latest-funding-round-was-unplanned-prompted-by-news-report',
}
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(lambda kv:get(*kv),urls.items()));(p/'extra_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
