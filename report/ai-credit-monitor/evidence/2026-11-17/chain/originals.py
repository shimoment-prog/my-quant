import concurrent.futures
import datetime
from html import unescape
import json
from pathlib import Path
import re
import urllib.request

p = Path(__file__).parent
sources = {
 'blackstone_yahoo':'https://finance.yahoo.com/real-estate/articles/blackstone-digital-infrastructure-trust-acquire-151500334.html',
 'blackstone_bxdc':'https://www.bxdc.com/news/blackstone-digital-infrastructure-trust-announces-5-billion-acquisition-of-stabilized-data-center-portfolio/',
 'telus_fp':'https://financialpost.com/real-estate/telus-drops-involvement-two-planned-ai-data-centres-vancouver',
 'telus_mapleridge':'https://www.mapleridgenews.com/business/telus-backs-out-of-vancouver-ai-data-centre-projects-8528348',
 'amd_acquisition':'https://ir.amd.com/news-events/press-releases/detail/1306/amd-completes-acquisition-of-world-labs',
 'marvell_penguin':'https://investor.marvell.com/news-events/press-releases/detail/1044/marvell-and-penguin-solutions-collaborate-to-address-data-center-ai-memory-and-accelerate-inference-at-scale',
 'amd_8ka_retry':'https://www.sec.gov/Archives/edgar/data/2488/000119312526462340/d105780d8ka.htm'
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
