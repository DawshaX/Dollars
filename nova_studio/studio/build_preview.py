"""Bounded local render smoke test. No network, upload or paid services."""
import subprocess,shutil,pathlib,sys,wave,math,struct,json
root=pathlib.Path(__file__).resolve().parents[1]
for tool in ['blender','ffmpeg','ffprobe']:
 if not shutil.which(tool):raise SystemExit('Missing required tool: '+tool)
subprocess.run(['blender','-b','-t','4','-P','scenes/render_preview.py'],cwd=root,check=True,timeout=1200)
audio=root/'renders/preview.wav';sr=44100
with wave.open(str(audio),'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr)
 samples=[]
 for i in range(sr*4):
  t=i/sr;env=min(t/.3,1,(4-t)/.5);tone=sum(math.sin(2*math.pi*f*t)*v for f,v in [(220,.06),(330,.025),(440,.015)])
  samples.append(struct.pack('<h',int(32767*env*tone)))
 w.writeframes(b''.join(samples))
out=root/'renders/NOVA_ENGINE_TEST.mp4'
subprocess.run(['ffmpeg','-y','-framerate','12','-i',str(root/'renders/preview/frame_%04d.png'),'-i',str(audio),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest','-movflags','+faststart',str(out)],check=True,timeout=120)
r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out)],capture_output=True,text=True,check=True)
data=json.loads(r.stdout);types={s['codec_type'] for s in data['streams']}
assert {'audio','video'}<=types
assert 3.8<=float(data['format']['duration'])<=4.3
(root/'renders/validation.json').write_text(json.dumps({'technical_smoke_test':'PASS','duration':data['format']['duration'],'human_visual_review':False,'publication_approved':False,'note':'Low resolution 4-second engine test, not a finished cinematic pilot'},indent=2))
print('PREVIEW_READY',out)
