"""Authored story planning and durable continuity, not automatic film generation."""
import sqlite3,json,pathlib,hashlib
from .core import CHANNEL
WORLD=json.loads((pathlib.Path(__file__).resolve().parents[1]/'content/world.json').read_text())
STORIES={
 'lost_sun':{'requires':{},'effect':{'sun_repaired':True},'goal':'Return light to the city',
 'beats':[
 ('hook','A tiny sun flickers above a dark glass street.','macro reveal','faint failing hum'),
 ('goal','The caretaker tries to lift a fallen prism toward the sun.','low medium','ceramic steps and glass contact'),
 ('obstacle','The prism is too heavy and slips onto a soft moss bed.','locked wide','soft impact then pause'),
 ('discovery','A puddle reflects a beam onto the prism. The caretaker notices.','eyeline insert','small clear chime'),
 ('solution','The caretaker tilts the prism using a lever, redirecting the beam.','side tracking','lever creak and rising harmonic'),
 ('payoff','The sun brightens and windows glow along the street.','pullback','warm restrained resolution')]},
 'quiet_canal':{'requires':{'sun_repaired':True},'effect':{'canal_open':True},'goal':'Bring water back to the garden canal',
 'beats':[
 ('hook','A dry canal ends beside a single drooping leaf.','macro','single dry leaf rustle'),
 ('goal','The caretaker follows empty channels toward the reservoir.','tracking','steps and distant water'),
 ('obstacle','A round pebble blocks the narrow gate.','wide','water pressure behind stone'),
 ('discovery','A floating seed spins and suggests a wheel.','insert','gentle water ticks'),
 ('solution','A small paddle wheel lifts the gate gradually.','side medium','synchronized wood and water'),
 ('payoff','Water reaches the leaf and its stem rises.','pullback','stream and quiet tonal resolve')]}}
class WorldMemory:
 def __init__(self,path):
  self.db=sqlite3.connect(path)
  self.db.execute('CREATE TABLE IF NOT EXISTS continuity(key TEXT PRIMARY KEY,value TEXT)')
  self.db.execute('CREATE TABLE IF NOT EXISTS episodes(fingerprint TEXT PRIMARY KEY,story TEXT,kind TEXT,plan TEXT,state TEXT,video_id TEXT UNIQUE)')
  with self.db:
   for k,v in WORLD['continuity_initial'].items():self.db.execute('INSERT OR IGNORE INTO continuity VALUES(?,?)',(k,json.dumps(v)))
 def state(self):return {k:json.loads(v) for k,v in self.db.execute('SELECT key,value FROM continuity')}
 def plan(self,story_id,kind='short'):
  if kind not in ('short','long'):raise ValueError('Unknown format')
  story=STORIES[story_id]
  if any(self.state().get(k)!=v for k,v in story['requires'].items()):raise ValueError('Continuity prerequisite not yet published')
  # Same underlying story cannot be emitted again just by changing format/color.
  fingerprint=hashlib.sha256((WORLD['world_id']+':'+story_id).encode()).hexdigest()
  if kind=='short':
   beats=[{'shot':i+1,'duration_seconds':4,'action':a,'camera':c,'sound':s,'beat':b} for i,(b,a,c,s) in enumerate(story['beats'])]
  else:
   raise ValueError('Long-form authored expansion not implemented; refuse padding a short')
  plan={'channel':CHANNEL,'world':WORLD['world_id'],'character_id':WORLD['character']['id'],'story_id':story_id,'kind':kind,'goal':story['goal'],'duration_seconds':sum(b['duration_seconds'] for b in beats),'shots':beats,'continuity_effect':story['effect'],'state':'storyboard_required','rendered':False,'publication_approved':False}
  with self.db:self.db.execute("INSERT INTO episodes VALUES(?,?,?,?,'planned',NULL)",(fingerprint,story_id,kind,json.dumps(plan)))
  return fingerprint,plan
 def confirm_publication(self,fingerprint,video_id,verified_channel):
  if verified_channel!=CHANNEL:raise ValueError('Wrong channel')
  if not isinstance(video_id,str) or len(video_id)!=11 or any(not(c.isalnum() or c in '_-') for c in video_id):raise ValueError('Invalid video ID')
  with self.db:
   row=self.db.execute("SELECT plan FROM episodes WHERE fingerprint=? AND state='planned'",(fingerprint,)).fetchone()
   if not row:raise ValueError('Episode missing or already confirmed')
   plan=json.loads(row[0])
   self.db.execute("UPDATE episodes SET state='published',video_id=? WHERE fingerprint=?",(video_id,fingerprint))
   for k,v in plan['continuity_effect'].items():self.db.execute('UPDATE continuity SET value=? WHERE key=?',(json.dumps(v),k))
 def close(self):self.db.close()
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--db',default='world.sqlite');p.add_argument('--out',default='story_plans');a=p.parse_args();m=WorldMemory(a.db)
 try:
  fingerprint,plan=m.plan('lost_sun');d=pathlib.Path(a.out);d.mkdir(parents=True,exist_ok=True);f=d/(fingerprint[:12]+'.json');f.write_text(json.dumps(plan,ensure_ascii=False,indent=2));print(f)
 finally:m.close()
