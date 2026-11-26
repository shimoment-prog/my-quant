import urllib.request,concurrent.futures,json,re,html,datetime
from pathlib import Path
b=Path('/private/tmp/ai-credit-monitor-2026-11-09/chain')
items={
 'edge_search':'https://theedgemalaysia.com/search-results?keywords=Goldman%20Apollo',
 'ft_search':'https://www.ft.com/search?q=Anthropic+generator',
 'stocktwits_search':'https://stocktwits.com/news-articles/markets/equity/the-ai-buildout-has-a-new-problem-and-its-not-nvidia-jpmorgan-sounds-alarm'
}
def f(z):
 k,u=z;r={'name':k,'url':u,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as h:s=h.read().decode('utf8','replace');r['final_url']=h.url
  (b/(k+'.html')).write_text(s)
  t=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',s,flags=re.S|re.I);t=html.unescape(re.sub(r'<[^>]+>',' ',t));t=re.sub(r'\s+',' ',t)
  (b/(k+'.txt')).write_text(t)
  r.update(ok=True,text=t[:23000],links=list(dict.fromkeys(html.unescape(x) for x in re.findall(r'href="([^\"]+)"',s)))[:170])
 except Exception as e:r.update(ok=False,error=str(e))
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rs=list(ex.map(f,items.items()))
(b/'site_search_manifest.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2))
for r in rs:print(json.dumps(r,ensure_ascii=False))
