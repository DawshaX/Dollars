"""Single-host render worker: queue -> render -> technical QC -> review.
Only supports the engine-test recipe. No upload path is called.
"""
import argparse,contextlib,fcntl,json,pathlib,shutil,sqlite3,subprocess,sys,threading,time
from .core import Studio,CHANNEL
ROOT=pathlib.Path(__file__).resolve().parents[1]
def probe(path):
 r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],check=True,capture_output=True,text=True,timeout=60)
 data=json.loads(r.stdout);streams=data.get('streams',[])
 video=next((s for s in streams if s.get('codec_type')=='video'),None)
 if not video or not any(s.get('codec_type')=='audio' for s in streams):raise ValueError('Missing audio/video stream')
 duration=float(data['format']['duration'])
 if not 3.9<=duration<=4.1:raise ValueError('Engine recipe duration mismatch')
 return {'duration_seconds':duration,'width':video['width'],'height':video['height'],'technical_pass':True,'editorial_pass':False,'engine_test':True,'publication_approved':False}
def run_one(db_path,output):
 db_path=pathlib.Path(db_path).resolve();output=pathlib.Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
 # Existing recipe uses shared render paths: serialize processes across databases too.
 with open(ROOT/'.render.lock','w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'state':'busy'}
  studio=Studio(str(db_path));job=studio.claim()
  if not job:studio.db.close();return {'state':'idle'}
  job_id,payload=job;folder=output/job_id;folder.mkdir(exist_ok=True)
  stop=threading.Event()
  def beat():
   while not stop.wait(30):
    db=sqlite3.connect(str(db_path),timeout=30)
    try:
     with db:db.execute("UPDATE jobs SET lease=? WHERE id=? AND state='running'",(time.time()+300,job_id))
    finally:db.close()
  thread=threading.Thread(target=beat,daemon=True);thread.start()
  def event(stage,**extra):
   with (folder/'events.jsonl').open('a') as f:f.write(json.dumps({'at':time.time(),'stage':stage,**extra})+'\n')
  try:
   if payload.get('channel')!=CHANNEL:raise ValueError('Channel mismatch')
   if payload.get('recipe')!='engine_test_v1':raise ValueError('No approved production renderer for this recipe')
   event('started');(folder/'brief.json').write_text(json.dumps(payload,indent=2))
   # Remove stale outputs so a failed run cannot pass on an older video.
   for name in ['NOVA_ENGINE_TEST.mp4','validation.json']:
    (ROOT/'renders'/name).unlink(missing_ok=True)
   event('render_audio_encode')
   with (folder/'build.log').open('w') as log:
    subprocess.run([sys.executable,'-m','studio.build_preview'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
   source=ROOT/'renders/NOVA_ENGINE_TEST.mp4';qc=probe(source);event('technical_qc',result=qc)
   # Decode every frame to detect basic media corruption; not artistic QC.
   subprocess.run(['ffmpeg','-v','error','-i',str(source),'-f','null','-'],check=True,capture_output=True,timeout=120)
   shutil.copy2(source,folder/'preview.mp4');(folder/'quality.json').write_text(json.dumps(qc,indent=2))
   studio.finish(job_id,'review','Render and full decode passed; engine test only; no publication approval')
   event('awaiting_review');return {'state':'review','job':job_id,'artifact':str(folder/'preview.mp4')}
  except Exception as exc:
   # Avoid propagating subprocess output or environment into public logs.
   error=type(exc).__name__
   studio.finish(job_id,'failed',error);event('failed',error_type=error)
   return {'state':'failed','job':job_id,'error_type':error}
  finally:stop.set();thread.join(timeout=2);studio.db.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',default='render_jobs.sqlite');p.add_argument('--output',default='render_jobs');p.add_argument('--seed-test',action='store_true');p.add_argument('--max-jobs',type=int,default=1);a=p.parse_args()
 if not 1<=a.max_jobs<=10:p.error('max-jobs must be 1..10')
 if a.seed_test:
  s=Studio(a.db)
  try:s.add('engine-test-worker-v1',{'channel':CHANNEL,'recipe':'engine_test_v1','engine_test':True,'publication_approved':False})
  except sqlite3.IntegrityError:pass
  finally:s.db.close()
 for _ in range(a.max_jobs):
  result=run_one(a.db,a.output);print(json.dumps(result),flush=True)
  if result['state'] in ['idle','busy','failed']:break
if __name__=='__main__':main()
