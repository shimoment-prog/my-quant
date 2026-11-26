import concurrent.futures
import datetime
from html import unescape
import json
from pathlib import Path
import re
import urllib.request

p = Path(__file__).parent
sources = {
    'nebius_Q3_release': 'https://nebius.com/newsroom/nebius-reports-third-quarter-2026-financial-results',
    'nebius_financials': 'https://nebius.com/financials',
    'nebius_6k_early': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126008/tm2629571d1_6k.htm',
    'nebius_6k_late': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126238/nbis-20261112x6k.htm',
    'nebius_citi': 'https://nebius.com/newsroom/nebius-secures-3-5-billion-financing-facility-with-citi'
}

def fetch(entry):
    name, url = entry
    result = {'name': name, 'url': url, 'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Public financial research analyst research@example.com' if 'sec.gov' in url else 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            result['final_url'] = response.url
        (p / (name + '.html')).write_bytes(raw)
        html = raw.decode('utf-8', 'replace')
        result['links'] = [{'url': unescape(m[1]), 'text': re.sub(r'\s+', ' ', unescape(re.sub('<[^>]+>', ' ', m[2]))).strip()[:180]} for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S|re.I) if re.search('pdf|exhibit|ex99|quarter|2026|shareholder',m[0],re.I)][:50]
        text = re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>', ' ', html, flags=re.S|re.I)
        text = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', text)))
        (p / (name + '.txt')).write_text(text)
        result.update(ok=True, chars=len(text), preview=text[:14000])
    except Exception as error:
        result.update(ok=False, error=str(error))
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(fetch, sources.items()))
(p / 'nebius_manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
for result in results:
    print(json.dumps(result, ensure_ascii=False))
