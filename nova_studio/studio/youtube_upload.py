"""Guarded single-upload adapter. Never invoked by scheduler automatically.
Secrets from process environment only. No token values are logged.
Uncertain uploads fail closed and require reconciliation, not blind retry.
"""
import os,json,urllib.request,urllib.error,pathlib,hashlib,sqlite3,subprocess
from .core import CHANNEL
from .schedule import validate_duration
API='https://www.googleapis.com/youtube/v3'
def request_json(url,method='GET',body=None,headers=None):
 h=dict(headers or {})
 if body is not None:h['Content-Type']='application/json'
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
 try:
  with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError('YouTube HTTP '+str(e.code)+'; response omitted to protect credentials') from None
def access_token():
 import urllib.parse
 values={k:os.environ.get(k,'') for k in ['YOUTUBE_CLIENT_ID','YOUTUBE_CLIENT_SECRET','YOUTUBE_REFRESH_TOKEN']}
 if not all(values.values()):raise RuntimeError('Missing YouTube OAuth credentials')
 data=urllib.parse.urlencode({'client_id':values['YOUTUBE_CLIENT_ID'],'client_secret':values['YOUTUBE_CLIENT_SECRET'],'refresh_token':values['YOUTUBE_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
 try:
  with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data),timeout=30) as r:t=json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError('OAuth HTTP '+str(e.code)) from None
 return t['access_token']
def verify_channel(token):
 d=request_json(API+'/channels?part=id,snippet&mine=true',headers={'Authorization':'Bearer '+token})
 items=d.get('items',[])
 if len(items)!=1 or items[0].get('id')!=CHANNEL:raise RuntimeError('OAuth destination is not the authorized channel')
 return items[0]['id']
def validate(path,meta):
 if meta.get('channel')!=CHANNEL:raise ValueError('Channel mismatch')
 if meta.get('engine_test') is not False:raise ValueError('Engine tests or unclassified artifacts cannot be uploaded')
 if not all(meta.get(k) is True for k in ['rights_reviewed','visual_reviewed','audio_reviewed','story_reviewed']):raise ValueError('Review gate incomplete')
 if not meta.get('title') or len(meta['title'])>100:raise ValueError('Invalid title')
 if len(meta.get('description',''))>5000:raise ValueError('Description too long')
 if type(meta.get('made_for_kids')) is not bool:raise ValueError('Audience classification required')
 if type(meta.get('contains_synthetic_media')) is not bool:raise ValueError('Synthetic-media classification required')
 r=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=60)
 data=json.loads(r.stdout);duration=float(data['format']['duration']);streams=data['streams'];video=next((s for s in streams if s.get('codec_type')=='video'),None)
 if not video or not any(s.get('codec_type')=='audio' for s in streams):raise ValueError('Audio/video streams required')
 if not validate_duration(meta.get('kind'),duration):raise ValueError('Duration outside production policy')
 if meta['kind']=='short' and video.get('height',0)<video.get('width',0):raise ValueError('Short must be square or vertical')
 # ffprobe metadata alone cannot detect bad frames or poor storytelling.
 return duration
def upload(path,meta,ledger='upload.sqlite'):
 if os.environ.get('NOVA_ENABLE_UPLOAD')!='1':raise RuntimeError('Upload activation flag not set')
 path=pathlib.Path(path);validate(path,meta)
 token=access_token();verify_channel(token)
 digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
 db=sqlite3.connect(ledger)
 db.execute('CREATE TABLE IF NOT EXISTS uploads(digest TEXT PRIMARY KEY,state TEXT,video_id TEXT)')
 with db:
  if db.execute('SELECT state FROM uploads WHERE digest=?',(digest,)).fetchone():raise RuntimeError('Artifact previously attempted; reconcile ledger before retry')
  db.execute("INSERT INTO uploads VALUES(?,'pending',NULL)",(digest,))
 body={'snippet':{'title':meta['title'],'description':meta.get('description',''),'categoryId':meta.get('category_id','24')},'status':{'privacyStatus':'public','selfDeclaredMadeForKids':meta['made_for_kids'],'containsSyntheticMedia':meta['contains_synthetic_media']}}
 try:
  req=urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','X-Upload-Content-Length':str(path.stat().st_size),'X-Upload-Content-Type':'video/mp4'})
  with urllib.request.urlopen(req,timeout=60) as r:location=r.headers.get('Location')
  from urllib.parse import urlsplit
  parsed=urlsplit(location or '')
  if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com'):raise RuntimeError('Unexpected upload endpoint')
  # Single PUT, bounded by artifact size gate; no automatic uncertain retries.
  if path.stat().st_size>256*1024*1024:raise RuntimeError('Artifact exceeds prototype 256 MiB upload limit')
  req=urllib.request.Request(location,data=path.read_bytes(),method='PUT',headers={'Content-Type':'video/mp4'})
  with urllib.request.urlopen(req,timeout=600) as r:result=json.load(r)
  video_id=result.get('id')
  if not video_id:raise RuntimeError('No video ID returned')
  with db:db.execute("UPDATE uploads SET state='uploaded',video_id=? WHERE digest=?",(video_id,digest))
  return {'video_id':video_id,'channel':CHANNEL}
 except Exception:
  with db:db.execute("UPDATE uploads SET state='uncertain' WHERE digest=?",(digest,))
  raise RuntimeError('Upload did not complete cleanly; reconcile before retry. Sensitive response omitted.') from None
 finally:db.close()
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('metadata');p.add_argument('--ledger',default='upload.sqlite');a=p.parse_args()
 print(json.dumps(upload(a.video,json.loads(pathlib.Path(a.metadata).read_text()),a.ledger)))
