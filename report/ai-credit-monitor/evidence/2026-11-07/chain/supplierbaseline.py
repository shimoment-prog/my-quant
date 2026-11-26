exec(open('/private/tmp/ai-credit-monitor-2026-11-07/chain/docs.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
items={'aaoi_8k_historical':'https://www.sec.gov/Archives/edgar/data/1158114/000168316826008351/aaoi_8k.htm'}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:r=list(ex.map(fetch,items.items()))
(b/'supplier_baseline_manifest.json').write_text(json.dumps(r,indent=2))
s=BeautifulSoup((b/'aaoi_8k_historical.html').read_bytes(),'html.parser')
for a in s.find_all('a',href=True):
 if '.htm' in a['href']:print(a.get_text(' ',strip=True),a['href'])
