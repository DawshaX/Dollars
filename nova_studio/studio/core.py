"""NOVA prototype: local durable queue. No network or publishing side effects."""
import sqlite3,json,time,uuid
CHANNEL='UCG9g_26H65D3FahqyiYPHAw'
class Studio:
 def __init__(self,path='nova.sqlite'):
  self.db=sqlite3.connect(path)
  self.db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, payload TEXT, state TEXT, attempts INTEGER DEFAULT 0, lease REAL, error TEXT)')
  self.db.execute('CREATE TABLE IF NOT EXISTS events(at REAL, job TEXT, message TEXT)')
  self.db.commit()
 def add(self,fingerprint,payload):
  if payload.get('channel')!=CHANNEL: raise ValueError('Wrong or missing channel')
  i=uuid.uuid4().hex
  with self.db:
   self.db.execute('INSERT INTO jobs(id,fingerprint,payload,state) VALUES(?,?,?,?)',(i,fingerprint,json.dumps(payload),'queued'))
  return i
 def claim(self):
  self.db.execute('BEGIN IMMEDIATE')
  try:
   self.db.execute("UPDATE jobs SET state='queued',lease=NULL WHERE state='running' AND lease<? AND attempts<3",(time.time(),))
   self.db.execute("UPDATE jobs SET state='failed',error='Lease expired; retry budget exhausted' WHERE state='running' AND lease<? AND attempts>=3",(time.time(),))
   row=self.db.execute("SELECT id,payload FROM jobs WHERE state='queued' AND attempts<3 ORDER BY rowid LIMIT 1").fetchone()
   if row:self.db.execute("UPDATE jobs SET state='running', attempts=attempts+1,lease=? WHERE id=?",(time.time()+300,row[0]))
   self.db.commit();return (row[0],json.loads(row[1])) if row else None
  except: self.db.rollback();raise
 def finish(self,i,state,message=''):
  if state not in ('review','failed'):raise ValueError('Invalid terminal state')
  with self.db:
   r=self.db.execute("UPDATE jobs SET state=?,lease=NULL,error=? WHERE id=? AND state='running'",(state,message,i))
   if r.rowcount!=1:raise ValueError('Job not running')
   self.db.execute('INSERT INTO events VALUES(?,?,?)',(time.time(),i,message))
 def status(self):return self.db.execute('SELECT state,count(*) FROM jobs GROUP BY state').fetchall()
def quality(meta):
 errors=[]
 if meta.get('channel')!=CHANNEL:errors.append('channel_mismatch')
 for field in ['rights_reviewed','visual_reviewed','audio_reviewed','story_reviewed']:
  if meta.get(field) is not True: errors.append(field)
 return errors
def publish(*args,**kwargs):
 raise RuntimeError('Publishing adapter deliberately not implemented; production authorization and validation required')
