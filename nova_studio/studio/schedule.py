"""Deterministic planning only. Never uploads or enables remote workflows."""
import json,pathlib,datetime,sqlite3
from .core import CHANNEL
POLICY=json.loads(pathlib.Path(__file__).with_name('production_policy.json').read_text())
def slots(anchor,start,end):
 if any(d.tzinfo is None or d.utcoffset() is None for d in [anchor,start,end]):raise ValueError('Timezone-aware dates required')
 if end<=start:raise ValueError('Invalid window')
 result=[]
 for kind,rule in POLICY['formats'].items():
  interval=datetime.timedelta(hours=rule['interval_hours'])
  n=max(0,int((start-anchor)//interval))
  at=anchor+n*interval
  if at<start:at+=interval
  while at<end:
   result.append({'kind':kind,'at':at.astimezone(datetime.timezone.utc).isoformat(),'min_seconds':rule['min_seconds'],'max_seconds':rule['max_seconds']})
   at+=interval
 return sorted(result,key=lambda x:(x['at'],x['kind']))
def enqueue(studio,planned):
 added=0
 for slot in planned:
  try:
   studio.add('slot:'+slot['kind']+':'+slot['at'],{'channel':CHANNEL,'schedule':slot,'stage':'needs_original_story','publishing_enabled':False});added+=1
  except sqlite3.IntegrityError:pass
 return added
def validate_duration(kind,seconds):
 rule=POLICY['formats'].get(kind)
 if rule is None or isinstance(seconds,bool) or not isinstance(seconds,(int,float)):return False
 return rule['min_seconds']<=seconds<=rule['max_seconds']
