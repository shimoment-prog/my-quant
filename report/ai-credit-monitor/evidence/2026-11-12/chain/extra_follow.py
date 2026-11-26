import urllib.request,urllib.parse,concurrent.futures,datetime,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from html import unescape
b=Path("/Users/richao11/myproject/my-quant/report/ai-credit-monitor/evidence/2026-11-12/chain")
urls={"iren_ir_fixed":"https://iren.com/investors/news","wulf_ir_fixed":"https://investors.terawulf.com/news-events/press-releases","mercor_alt":"https://www.alternativeswatch.com/2026/11/10/apollo-mercor-seried-d-750-m-kkr-midland-basis/","mercor_blog":"https://www.mercor.com/blog","toms_home":"https://www.tomshardware.com/"}
def f(z):
 k,u=z;r={"name":k,"url":u,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as h:d=h.read();r["final_url"]=h.url
  (b/(k+".html")).write_bytes(d);s=d.decode("utf-8","replace");r["links"]=[{"url":unescape(m[1]),"text":unescape(re.sub("<[^>]+>"," ",m[2])).strip()[:220]} for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",s,re.S|re.I) if re.search("invest|news|750|Apollo|turbine|softbank",m[0],re.I)][:80]
  if "rss" in u:
   x=ET.fromstring(d);r["items"]=[{v:i.findtext(v) for v in ["title","link","pubDate","source"]} for i in x.findall("./channel/item")][:20]
  s=re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>"," ",s,flags=re.S|re.I);s=unescape(re.sub(r"<[^>]+>"," ",s));s=re.sub(r"\s+"," ",s);(b/(k+".txt")).write_text(s);r.update(ok=True,chars=len(s))
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:out=list(ex.map(f,urls.items()))
(b/"extra_follow_manifest.json").write_text(json.dumps(out,indent=2))
for r in out:print(json.dumps(r))
