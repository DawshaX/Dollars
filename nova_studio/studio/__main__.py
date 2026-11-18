import argparse,json,pathlib
from .core import Studio,CHANNEL
p=argparse.ArgumentParser();p.add_argument('command',choices=['seed','step','status']);p.add_argument('--db',default='nova.sqlite');p.add_argument('--output',default='work');a=p.parse_args();s=Studio(a.db)
if a.command=='seed':
 for slug,title in [('glass-garden','A drop awakens a glass garden'),('little-star','A tiny traveller returns a lost star'),('sand-orbit','Sand assembles an impossible orbit')]:
  try:s.add(slug,{'channel':CHANNEL,'title':title,'format':'short','duration_seconds':25,'publishing_enabled':False})
  except Exception as e:
   import sqlite3
   if not isinstance(e,sqlite3.IntegrityError):raise
elif a.command=='step':
 job=s.claim()
 if job:
  i,payload=job
  try:
   d=pathlib.Path(a.output)/i;d.mkdir(parents=True,exist_ok=True)
   payload.update({'stage':'preproduction_only','rendered':False,'review_required':True,'beats':['establish goal','obstacle','discovery','resolution'],'next_action':'Create and review animatic; render using Blender; review audio and rights'})
   (d/'brief.json').write_text(json.dumps(payload,indent=2))
   s.finish(i,'review','Preproduction brief created; NOT a rendered video')
  except Exception as e:s.finish(i,'failed',str(e));raise
print(json.dumps(s.status()))
