import urllib.request,urllib.parse,pathlib,datetime,json,concurrent.futures,xml.etree.ElementTree as E,re,html
p=pathlib.Path('/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-15/bigtech')
us={'anthropic_axios': 'https://www.axios.com/2026/11/13/anthropic-ipo-nvidia-jensen-huang', 'anthropic_mixup': 'https://beincrypto.com/anthropic-cuts-ipo-cramer-deal-wobbles/', 'meta_alberta_link': 'https://news.google.com/rss/articles/CBMinAFBVV95cUxOeHpJcTRfS0hLbWRWNWpadFdJOHZBaFNyUTdaUkh5ZFRSN25wTGRwNHBRZXRwVHBXR3ZQRHhWZXJ5MjNVRG5nZzU4bE1wc2RlRWhPdF9BdkNtbk9NTFNveXRvNTNoaHJheFV5SG5LQlM1Vzg3M1VWZVFYUGFiLVp4eWYxaVctcHkzdGxRREpDTnJrQnNLcC1XQlllQkc?oc=5', 'amazon_uae_link': 'https://news.google.com/rss/articles/CBMilgJBVV95cUxNd283UlpHT0ZOOUd0d0tOSkQwRF84U3ZDZzE1ZElXSmgxUU9zVXdrYlhqMTlzYWdNZkxyOWVmS3JxUWZ2NF9hMTA4ZjFKOGoxbWN3RV80Qkdyak9kbzlVZzRFZUVfajd6Mi0zWnppTk9LV0pXcGJEMDJDQVlHMGctbDVzRl9sZWtWMzVsWENqRGE4di1zT3hHUzNRMTlxWXFzMHBVemlOMGVxX0MwNTNIOWR3ZDVUVC1TQjZGY0d3T1FhQUVKbEpsblhLYzdaV0JqclZ1ZkU5TE80bE5adE9rXzhuV3RJYlpTZzIzZWhDMWFpZFJmaTZxWnZPZGttWV9iYXhYemo0cUZzbHVwVkF5QTdTeTVfZw?oc=5'}

def f(it):
 n,u=it;t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  raw=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Personal research contact analyst@example.com'}),timeout=15).read();(p/(n+'.html')).write_bytes(raw);s=raw.decode('utf-8','replace');s=re.sub(r'<(script|style)\b.*?</\1>','',s,flags=re.S|re.I);s=html.unescape(re.sub('<[^>]+>',' ',s));s=re.sub(r'\s+',' ',s);(p/(n+'.txt')).write_text(s);a=[]
  try:
   for x in E.fromstring(raw).findall('./channel/item')[:20]:a.append({'published_at':x.findtext('pubDate'),'title':x.findtext('title'),'url':x.findtext('link')})
  except:pass
  return {'name':n,'url':u,'retrieved_at':t,'ok':True,'items':a,'textlength':len(s)}
 except Exception as e:return {'name':n,'url':u,'retrieved_at':t,'ok':False,'error':str(e)}
a=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(f,us.items()));(p/'primary_manifest.json').write_text(json.dumps(a,ensure_ascii=False,indent=2));print(json.dumps(a,ensure_ascii=False,indent=2))
