exec(open('/private/tmp/ai-credit-monitor-2026-11-07/chain/docs.py').read().split('with concurrent.futures.ThreadPoolExecutor')[0])
items={'wulf_release':'https://www.sec.gov/Archives/edgar/data/1083301/000162828026071306/a_wulfearningsreleaseq32026.htm'}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:r=list(ex.map(fetch,items.items()))
(b/'release_manifest.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
