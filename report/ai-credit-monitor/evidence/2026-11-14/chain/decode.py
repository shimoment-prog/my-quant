import concurrent.futures
import datetime
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

p = Path(__file__).parent
feeds = json.loads((p / 'qts_smfg_news_manifest.json').read_text())
items = [('qts_ms', feeds[0]['items'][0]), ('qts_bt', feeds[0]['items'][1]),
         ('smfg_tv', feeds[1]['items'][0]), ('smfg_fini', feeds[1]['items'][1])]

def decode(entry):
    name, item = entry
    result = {'name': name, 'title': item['title'], 'published_at': item['pubDate'],
              'source_feed_url': item['link'],
              'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(item['link'], headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(request, timeout=15).read().decode()
        (p / (name + '_gurl.html')).write_text(html)
        article_id = re.search('data-n-a-id="([^"]+)"', html)[1]
        timestamp = re.search('data-n-a-ts="([^"]+)"', html)[1]
        signature = re.search('data-n-a-sg="([^"]+)"', html)[1]
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

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(decode, items))
(p / 'decode_manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
for result in results:
    print(json.dumps(result, ensure_ascii=False))
