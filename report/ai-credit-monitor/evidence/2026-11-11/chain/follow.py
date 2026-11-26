import urllib.request,urllib.parse,concurrent.futures,datetime,json,re
from pathlib import Path
from html import unescape
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-11/chain")
urls={"mrvl425_1":"https://www.sec.gov/Archives/edgar/data/1835632/000119312526455438/d172329d425.htm","mrvl425_2":"https://www.sec.gov/Archives/edgar/data/1835632/000119312526455426/d162070d425.htm","mrvl425_3":"https://www.sec.gov/Archives/edgar/data/1835632/000119312526455400/d180177d425.htm","apollo424b5":"https://www.sec.gov/Archives/edgar/data/1858681/000119312526455504/d193679d424b5.htm","softbank_financials":"https://group.softbank/en/ir/financials","softbank_news":"https://group.softbank/en/news/press","ked_home":"https://www.kedglobal.com/","softbank_search":"https://www.google.com/search?q="+urllib.parse.quote('SoftBank "7 Billion" "Data Center" November 10 2026'),"ked_search":"https://www.google.com/search?q="+urllib.parse.quote('"Anthropic setback exposes cracks"')}
def f(z):
 k,u=z;r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Public analyst contact research@example.com" if "sec.gov" in u else "Mozilla/5.0"}),timeout=18) as h:d=h.read();r["final_url"]=h.url
  (b/(k+".html")).write_bytes(d);s=d.decode("utf-8","replace");s=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>"," ",s,flags=re.S|re.I);s=unescape(re.sub(r"<[^>]+>"," ",s));s=re.sub(r"\s+"," ",s);(b/(k+".txt")).write_text(s);r.update(ok=True,chars=len(s),text_preview=s[:1200])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=list(ex.map(f,urls.items()))
(b/"follow_manifest.json").write_text(json.dumps(out,indent=2))
for r in out:print(json.dumps(r))
