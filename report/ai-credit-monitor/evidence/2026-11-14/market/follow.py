import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
from html.parser import HTMLParser

ROOT = Path(__file__).parent

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ['script','style']: self.skip += 1
    def handle_endtag(self, tag):
        if tag in ['script','style']: self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

URLS={
 'fred_ig_retry':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLC0A0CM&cosd=2026-09-01',
 'fred_hy_retry':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2&cosd=2026-09-01',
 'fed_fsr':'https://www.federalreserve.gov/publications/financial-stability-report.htm',
 'fed_press':'https://www.federalreserve.gov/newsevents/pressreleases.htm',
 'fed_fsr_nov2026':'https://www.federalreserve.gov/publications/files/financial-stability-report-20261113.pdf',
}

def fetch(item):
    key,url=item
    is_csv=key.startswith('fred')
    is_pdf=url.endswith('.pdf')
    file=key+('.csv' if is_csv else '.pdf' if is_pdf else '.html')
    record={'id':key,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'file':file}
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
            body=r.read(); record.update(ok=True,status=r.status,bytes=len(body))
        (ROOT/file).write_bytes(body)
        if not is_csv and not is_pdf:
            p=Text();p.feed(body.decode('utf-8',errors='replace'))
            (ROOT/(key+'.txt')).write_text('\n'.join(p.parts))
    except Exception as e: record.update(ok=False,error=str(e))
    return record

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    manifest=list(pool.map(fetch,URLS.items()))
(ROOT/'follow_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(manifest,ensure_ascii=False))
