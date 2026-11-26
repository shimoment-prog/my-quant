import concurrent.futures
import csv
import io
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).parent
PREVIOUS = ROOT.parent.parent / '2026-11-16' / 'market'
START = datetime.fromisoformat('2026-11-16T00:32:08.760704+00:00')
queries = {
    'news_credit': '(Oracle OR CoreWeave OR Meta OR Alphabet) (CDS OR "credit spread" OR "bond offering" OR "debt offering") when:2d',
    'news_chain': '("AI data center" OR "AI datacenter" OR "GPU loan") (default OR cancellation OR financing OR impairment OR delay) when:2d',
    'news_demand': '(Google OR Meta OR Microsoft OR Amazon) ("capital expenditure" OR capex OR "cloud demand" OR "data center") when:2d',
}
urls = {
    'fred_ig': 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLC0A0CM&cosd=2026-09-01',
    'fred_hy': 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2&cosd=2026-09-01',
    **{k: 'https://news.google.com/rss/search?q=' + quote(v) + '&hl=en-US&gl=US&ceid=US:en' for k, v in queries.items()},
}


def fetch(item):
    key, url = item
    filename = key + ('.csv' if key.startswith('fred') else '.xml')
    record = {'id': key, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'file': filename}
    try:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0 public financial research'})
        with urlopen(request, timeout=25) as result:
            content = result.read()
            record.update(status=result.status, ok=result.status == 200, bytes=len(content))
        (ROOT / filename).write_bytes(content)
    except Exception as exc:
        record.update(ok=False, error=str(exc))
    return record


with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    manifest = list(pool.map(fetch, urls.items()))
(ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
previous_proxies = {p['source_id']: p for p in json.loads((PREVIOUS / 'proxies.json').read_text())}
proxies = []
news = []
for record in manifest:
    if not record['ok']:
        continue
    if record['id'].startswith('fred'):
        rows = list(csv.DictReader(io.StringIO((ROOT / record['file']).read_text())))
        date_column, value_column = rows[0].keys()
        valid = []
        for row in rows:
            try:
                valid.append({'date': row[date_column], 'value': float(row[value_column]) * 100})
            except ValueError:
                pass
        latest, prior = valid[-1], valid[-2]
        earlier = valid[-21] if len(valid) >= 21 else None
        previous_run = previous_proxies[record['id']]
        proxy = {
            'id': value_column,
            'source_id': record['id'],
            'evidence_type': 'broad_market_proxy_not_AI_CDS',
            'unit': 'basis_points',
            'observation_date': latest['date'],
            'value': latest['value'],
            'previous_market_observation': prior,
            'change_bp_vs_previous_market_observation': round(latest['value'] - prior['value'], 6),
            'comparison_to_previous_monitor_run': {
                'date': previous_run['observation_date'], 'value': previous_run['value'],
                'new_market_observation': latest['date'] != previous_run['observation_date'],
                'value_change_bp': round(latest['value'] - previous_run['value'], 6),
            },
            'comparison_20_observations_earlier': None if earlier is None else {**earlier, 'change_bp': round(latest['value'] - earlier['value'], 6)},
            'source': 'https://fred.stlouisfed.org/series/' + value_column,
            'data_url': record['url'],
            'publication_at': None,
            'retrieved_at': record['retrieved_at'],
            'archived_csv': 'evidence/2026-11-17/market/' + record['file'],
            'recent_valid_observations': valid[-8:],
            'notes': ['Use actual FRED observation date; no interpolation of missing dates, no assertion of issuer CDS or CDX.IG.', '20 observations refers to published valid source observations, not exact calendar-month matched issuer trading data.'],
        }
        proxies.append(proxy)
    else:
        root = ET.fromstring((ROOT / record['file']).read_bytes())
        for item in root.findall('./channel/item'):
            try:
                published = parsedate_to_datetime(item.findtext('pubDate'))
            except Exception:
                continue
            if published < START:
                continue
            source = item.find('source')
            news.append({'query': record['id'], 'title': item.findtext('title'), 'url': item.findtext('link'), 'published_at': published.isoformat(), 'source': None if source is None else source.text, 'evidence_grade': 'RSS_discovery_only_not_verified_full_body'})
(ROOT / 'proxies.json').write_text(json.dumps(proxies, ensure_ascii=False, indent=2) + '\n')
(ROOT / 'incremental_news_items.json').write_text(json.dumps(news, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'manifest': manifest, 'proxies': proxies, 'incremental_news_items': news}, ensure_ascii=False))
