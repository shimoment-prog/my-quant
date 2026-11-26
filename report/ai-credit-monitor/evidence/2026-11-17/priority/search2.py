exec(open(__file__.replace('search2.py','fetch.py')).read().split('m=list(concurrent')[0])
urls={
'hsbc_bing':'https://www.bing.com/search?q='+urllib.parse.quote('"HSBC" "300 million" "AI" "loan"')+'&format=rss',
'hsbc_gnews_alt':'https://news.google.com/rss/search?q='+urllib.parse.quote('"HSBC offloads"')+'&hl=en-GB&gl=GB&ceid=GB:en',
'hsbc_investing_news':'https://www.investing.com/news/stock-market-news',
'openai_cfo_search':'https://www.bing.com/search?q='+urllib.parse.quote('OpenAI CFO latest funding round unplanned Semafor November 17 2026')+'&format=rss',
'coreweave_85_original':'https://app.dealroom.co/news/note/coreweave-lands-8-5b-debt-deal-cementing-a-trillion-dollar-ai-lending-playbook',
'blackstone_press':'https://www.blackstone.com/news/press/',
}
m=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(lambda kv:get(*kv),urls.items()));(p/'search2_manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
