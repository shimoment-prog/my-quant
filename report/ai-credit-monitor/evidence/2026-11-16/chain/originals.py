import concurrent.futures
import datetime
from html import unescape
import json
from pathlib import Path
import re
import urllib.request

p = Path(__file__).parent
sources = {
 'nvidia_tikr_funding': 'https://www.tikr.com/blog/neoclouds-are-nearly-half-of-nvidias-own-revenue-its-new-ceo-may-stop-funding-them',
 'iren_tipranks_call': 'https://www.tipranks.com/news/company-announcements/iren-earnings-call-highlights-ai-cloud-growth',
 'ares_cre_call': 'https://www.tipranks.com/news/company-announcements/ares-commercial-real-estate-earnings-call-resolutions-and-growth'
}
def fetch(entry):
    name, url = entry
    result = {'name': name, 'url': url, 'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            result['final_url'] = response.url
        (p / (name + '.html')).write_bytes(raw)
        text = re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>', ' ', raw.decode('utf-8', 'replace'), flags=re.S|re.I)
        text = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', text)))
        (p / (name + '.txt')).write_text(text)
        result.update(ok=True, chars=len(text), text=text[:18000])
    except Exception as error:
        result.update(ok=False, error=str(error))
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(fetch, sources.items()))
(p / 'originals_manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
for result in results:
    print(json.dumps(result, ensure_ascii=False))
