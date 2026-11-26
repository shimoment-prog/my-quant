import concurrent.futures
import datetime
from html import unescape
import json
from pathlib import Path
import re
import urllib.request

p = Path(__file__).parent
sources = {
 'nebius_Q3_SEC_release': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126008/tm2629571d1_ex99-1.htm',
 'nebius_Q3_SEC_letter': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126008/tm2629571d1_ex99-2.htm',
 'nebius_Q3_MD_and_A': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126238/nbis-ex99d1.htm',
 'nebius_Q3_SEC_statements': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926126238/nbis-ex99d2.htm',
 'nebius_Q2_6k': 'https://www.sec.gov/Archives/edgar/data/1513845/000110465926094568/tm2622968d1_6k.htm'
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
(p / 'nebius_exhibits_manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
for result in results:
    print(json.dumps(result, ensure_ascii=False))
