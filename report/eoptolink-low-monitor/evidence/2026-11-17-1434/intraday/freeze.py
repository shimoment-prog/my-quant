from pathlib import Path
from datetime import datetime, timedelta, timezone
import concurrent.futures as cf
import json
import re
import urllib.request

R = Path('/private/tmp/eoptolink-monitor-20261117-1430')
TZ = timezone(timedelta(hours=8))
urls = {'sina_final.txt': 'https://hq.sinajs.cn/list=sz300502,sz300308,sh515880,sz399006',
        'quotes_final.txt': 'https://qt.gtimg.cn/q=sz300502,sz300308,sh515880,sz399006'}

def fetch(item):
    name, url = item
    start = datetime.now(TZ)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'})
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read()
        (R / name).write_bytes(raw)
        return dict(name=name, url=url, ok=True, retrieved_at=datetime.now(TZ).isoformat(), started_at=start.isoformat())
    except Exception as e:
        return dict(name=name, url=url, ok=False, error=str(e), started_at=start.isoformat())

assert not (R / 'frozen_prediction.json').exists(), 'Do not replace a frozen prediction'
with cf.ThreadPoolExecutor(max_workers=2) as pool:
    manifest = list(pool.map(fetch, urls.items()))
(R / 'manifest_final.json').write_text(json.dumps(manifest, indent=2))
assert all(x['ok'] for x in manifest)
quotes = {}
for symbol, raw in re.findall(r'var hq_str_(\w+)="([^"]*)";', (R / 'sina_final.txt').read_bytes().decode('gb18030')):
    x = raw.split(',')
    t = x[30] + 'T' + x[31] + '+08:00'
    vol, amt, price, prev = float(x[8]), float(x[9]), float(x[3]), float(x[2])
    high, low = float(x[4]), float(x[5])
    quotes[symbol] = dict(name=x[0], symbol=symbol, price=price, previous_close=prev, open=float(x[1]),
        change_pct=(price / prev - 1) * 100, day_high=high, day_low=low, volume_shares=vol, amount_cny=amt,
        vwap=amt / vol if vol and symbol != 'sz399006' else None, quote_time=t, source='sina_final.txt',
        currency='CNY' if symbol != 'sz399006' else 'index_points',
        field_times=dict(price=t, change_pct=t, day_high_cumulative_through=t, day_low_cumulative_through=t,
            amount_cumulative_through=t, vwap_cumulative_through=t if symbol != 'sz399006' else None),
        exact_high_tick_time=None, exact_low_tick_time=None,
        vwap_method='cumulative amount(CNY) / cumulative volume(shares)' if symbol != 'sz399006' else 'not applicable to index',
        distance_from_fixed_line_yuan=price - 179.83 if symbol == 'sz300502' else None,
        distance_from_fixed_line_pct=(price / 179.83 - 1) * 100 if symbol == 'sz300502' else None,
        distance_above_day_low_yuan=price - low, distance_above_day_low_pct=(price / low - 1) * 100)
cross = {}
for symbol, raw in re.findall(r'v_(\w+)="([^"]*)";', (R / 'quotes_final.txt').read_bytes().decode('gb18030')):
    x = raw.split('~')
    cross[symbol] = dict(price=float(x[3]), day_high=float(x[33]), day_low=float(x[34]),
        quote_time=datetime.strptime(x[30], '%Y%m%d%H%M%S').replace(tzinfo=TZ).isoformat(), source='quotes_final.txt')

s = (R / 'm5.txt').read_text()
bars = json.loads(s[s.index('['):s.rindex(']') + 1])
today = [x for x in bars if x['day'].startswith('2026-11-17')]
completed = [x for x in today if x['day'] <= '2026-11-17 14:30:00']
unfinished = [x for x in today if x not in completed]
assert len(completed) == 42
q = quotes['sz300502']
qt = datetime.fromisoformat(q['quote_time'])
now = datetime.now(TZ)
assert now.date().isoformat() == '2026-11-17' and (14, 30) <= (now.hour, now.minute) < (15, 0)
assert 0 <= (now - qt).total_seconds() < 60 and qt.date() == now.date()
assert cross['sz300502']['day_low'] == q['day_low']
assert abs(cross['sz300502']['price'] / q['price'] - 1) < .003
assert q['price'] < q['vwap'] and q['distance_above_day_low_pct'] < 1 and q['price'] < 179.83
assert q['change_pct'] < quotes['sh515880']['change_pct'] and q['change_pct'] < quotes['sz399006']['change_pct']
L = q['day_low']
assert L < 157.76
deadline = now.replace(hour=15, minute=0, second=0, microsecond=0)
prediction = dict(id=now.strftime('%Y-%m-%d-%H%M') + '-L' + str(round(L * 100)), symbol='300502.SZ',
    scheduled_check_at='2026-11-17T14:30:00+08:00', triggered_at='2026-11-17T14:31:40.559+08:00',
    created_at=now.isoformat(), forecast_start=now.isoformat(), snapshot_time=q['quote_time'], threshold=L,
    comparison='strictly_less_than', event=f'Any traded price strictly below{L:.2f} after forecast_start and by deadline',
    deadline=deadline.isoformat(), risk='偏高', numeric_probability=None, model_validated=False,
    status='pending', settled=False,
    note='Independent afternoon forecast starts at actual creation, never backdated to14:30 or heartbeat time. Morning157.76 prediction keeps original threshold, risk and15:00deadline and is not finally settled. Price close to freshly frozen cumulative low, belowVWAP and weakerthanETF/ChiNext; recent completed reboundhighs declined. Short remaining window and latest completed pullback volume contraction are counterevidence. No tickstream in quote-to-creation gap; later reviews must not alter original threshold/window/risk.')
snapshot = dict(stamp=now.strftime('%Y-%m-%d-%H%M'), quotes=quotes, crosscheck_tencent=cross,
    quote_age_seconds=(now - qt).total_seconds(), frozen_prediction=prediction, completed_bars=completed,
    excluded_unfinished_bars=unfinished, structural_bar_cutoff='2026-11-17T14:30:00+08:00',
    source_timing_note='Structure from14:32:30fetch uses completed bars only through14:30. Final quote precedes actual forecast; later research does not change original threshold, risk or window.')
for name, obj in [('snapshot.json', snapshot), ('frozen_prediction.json', prediction)]:
    with (R / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')
print(json.dumps(dict(forecast=prediction, quotes=quotes, completed_bar_count=len(completed),
    quote_age_seconds=(now - qt).total_seconds()), ensure_ascii=False, indent=2))
