import json
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone
b=Path('/private/tmp/a-share-premarket-2026-11-12')
u='https://hq.sinajs.cn/list=hf_NQ,hf_ES,hf_YM'
r={'url':u,'retrieved_at':datetime.now(timezone.utc).isoformat()}
try:
 with urlopen(Request(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),timeout=15) as f:data=f.read();r['status']=f.status
 (b/'sina_futures.txt').write_text(data.decode('gb18030',errors='replace'))
 r['ok']=True
except Exception as e:r.update(ok=False,error=str(e))
(b/'futures_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps(r,ensure_ascii=False))
