import urllib.request,concurrent.futures,datetime,json,re
from pathlib import Path
from html import unescape
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-14/chain")
urls={"qts_bt_retry":"https://www.businesstimes.com.sg/companies-markets/blackstones-qts-cutting-ai-debt-sale-more-half","qts_traders":"https://tradersunion.com/news/financial-news/show/1129327-qts-cuts-private-debt-offering/","traders_home":"https://tradersunion.com/news/","qts_bing":"https://www.bing.com/search?q=QTS+cuts+private+debt+offering+300+million+November+13+2026","smfg_latest":"https://www.smfg.co.jp/english/investor/financial/latest_statement.html","smfg_bing":"https://www.bing.com/search?q=SMFG+tightens+data+center+financing+November+13+2026"}
def f(z):
 k,u=z;r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Public analyst contact research@example.com" if "sec.gov" in u else "Mozilla/5.0"}),timeout=18) as h:d=h.read();r["final_url"]=h.url
  (b/(k+".html")).write_bytes(d);s=d.decode("utf-8","replace");r["links"]=[{"url":unescape(m[1]),"text":unescape(re.sub("<[^>]+>"," ",m[2])).strip()[:180]} for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",s,re.S|re.I) if re.search("exhibit|ex-|press|news|billion|financ",m[0],re.I)][:35];s=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>"," ",s,flags=re.S|re.I);s=unescape(re.sub(r"<[^>]+>"," ",s));s=re.sub(r"\s+"," ",s);(b/(k+".txt")).write_text(s);r.update(ok=True,chars=len(s),preview=s[:2500])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=list(ex.map(f,urls.items()))
(b/"follow2_manifest.json").write_text(json.dumps(out,indent=2))
for r in out:print(json.dumps(r))
