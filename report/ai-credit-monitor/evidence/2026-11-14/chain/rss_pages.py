import urllib.request,concurrent.futures,datetime,json,re
from pathlib import Path
from html import unescape
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-14/chain")
urls={'qts_marketscreener_com': 'https://news.google.com/rss/articles/CBMisgFBVV95cUxNdnYtcGdZb0oyam9FOFFvV1BlX1V2aTZmNzRVWXVoZnVadlRMV2RQTjZUYXJ6ak5sSnNBWWZ2eXB0NjVhaW0zTU5wZmg4SXgyeHcyWGxsUGVYZ0MwLVNuSlpIZ21vZ2NPX1BtV0U3ejdLdEV5cUJHYUc2UjdFVHMyTXlvZkROaEJENFg4QlVyWVdGY0xrNzBKaFZ6QWplOU5UQXdVSHZFVEtFN1UtQTkzOU9B?oc=5', 'qts_The Business Times': 'https://news.google.com/rss/articles/CBMikgFBVV95cUxPcG1fc1pwTFR0RkNDTkoyOGlBcG5RSGgxNWY5dnlNMnY3VFpRVEU1RHlXRkU0WnQ1Y2JGcFZMTFBZRFNqYlpoYkJGWWo0Z09JZTgwWURwTm9GaGg3NTQ1X3hQRmhrVUlHaldxdmpsNU9BeTRJc2xqMEtiLWtIZ2VDOV9wRUFsaGpCY0c5aW8tWHJUdw?oc=5', 'smfg_TradingView': 'https://news.google.com/rss/articles/CBMi1wFBVV95cUxOTFBGVFdmRk9zS1M5R1pVM3J5YzR2alRzaDhLOE00YTVGZW9LUWdabTRmeE84R09xUWw5Z2dUYmI3THNkZVB6MHdoUWQ3UkJ0ZFFMbERaNlhzNlpnSWZqYllmaXdLb0ZGcFB3Y1J6ek9hVHFsUEp0dllwRkREa2p4X2Yyc2FKZVlPMFEyNi1lVGxJQnFjcFlRa0VrcGN2Qnd2aWsyLXo1N0cxTWcySkJNd0FQelZGQUI1Rnd0QWM5ZndoYmdoRnJtM2xjMzR6VHJGT2RBUzZyZw?oc=5'}
def f(z):
 k,u=z;r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Public analyst contact research@example.com" if "sec.gov" in u else "Mozilla/5.0"}),timeout=18) as h:d=h.read();r["final_url"]=h.url
  (b/(k+".html")).write_bytes(d);s=d.decode("utf-8","replace");r["links"]=[{"url":unescape(m[1]),"text":unescape(re.sub("<[^>]+>"," ",m[2])).strip()[:180]} for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",s,re.S|re.I) if re.search("exhibit|ex-|press|news|billion|financ",m[0],re.I)][:35];s=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>"," ",s,flags=re.S|re.I);s=unescape(re.sub(r"<[^>]+>"," ",s));s=re.sub(r"\s+"," ",s);(b/(k+".txt")).write_text(s);r.update(ok=True,chars=len(s),preview=s[:2500])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=list(ex.map(f,urls.items()))
(b/"rss_pages_manifest.json").write_text(json.dumps(out,indent=2))
for r in out:print(json.dumps(r))
