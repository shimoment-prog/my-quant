exec(open(__file__.replace('lastsearch.py','fetch.py')).read().split('m=list(concurrent')[0])
urls={}
for name,q in {'news_hsbc_all':'HSBC "data center" "discount" when:3d','news_hsbc_sold':'"HSBC Sold" "Loan" when:3d','news_openai_cfo':'"OpenAI CFO" "unplanned" when:2d','news_breit':'"Blackstone" "Amazon" "5 billion" when:2d'}.items():urls[name]='https://news.google.com/rss/search?q='+urllib.parse.quote(q)+'&hl=en-GB&gl=GB&ceid=GB:en'
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(lambda kv:get(*kv),urls.items()));(p/'lastsearch_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
