import concurrent.futures
import datetime
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

p = Path(__file__).parent
items = []
market=json.loads((p.parent/'market/incremental_news_items.json').read_text())
x=next(x for x in market if 'HSBC offloads' in x['title'])
items.append(('hsbc_investing',dict(title=x['title'],pubDate=x['published_at'],link=x['url'])))
for name,feed,frag in [('openai_cfo','news_openai.xml','OpenAI CFO says latest'),('breit_amazon','news_qts.xml','The Business Times')]:
 rows=[{k:x.findtext(k) for k in ['title','pubDate','link']} for x in ET.parse(p/feed).findall('.//item')]
 items.append((name,next(x for x in rows if frag in x['title'])))

def decode(entry):
    name, item = entry
    result = {'name': name, 'title': item['title'], 'published_at': item['pubDate'],
              'source_feed_url': item['link'],
              'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(item['link'], headers={'User-Agent': 'Mozilla/5.0'})
        raw = urllib.request.urlopen(request, timeout=15).read().decode()
        (p / (name + '_gurl.html')).write_text(raw)
        article_id = re.search('data-n-a-id="([^"]+)"', raw)[1]
        timestamp = re.search('data-n-a-ts="([^"]+)"', raw)[1]
        signature = re.search('data-n-a-sg="([^"]+)"', raw)[1]
        payload = ['garturlreq', [['X', 'X', ['X', 'X'], None, None, 1, 1, 'US:en',
                   None, 1, None, None, None, None, None, 0, None, None,
                   [1608992183, 723341000]], 'X', 'X', 1, [2, 3, 4, 8], 1, 0,
                   '655000234', 0, 0, None, 0], article_id, int(timestamp), signature]
        body = urllib.parse.urlencode({'f.req': json.dumps([
            [['Fbv4je', json.dumps(payload), None, 'generic']]])}).encode()
        request = urllib.request.Request(
            'https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je',
            data=body, headers={'User-Agent': 'Mozilla/5.0',
                                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
        decoded = urllib.request.urlopen(request, timeout=15).read().decode()
        (p / (name + '_decoded.txt')).write_text(decoded)
        result.update(decode_ok=True, result=decoded)
    except Exception as error:
        result.update(decode_ok=False, error=str(error))
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(decode, items))
(p / 'decode_manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
for result in results:
    print(json.dumps(result, ensure_ascii=False))
