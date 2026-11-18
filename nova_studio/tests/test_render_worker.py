import unittest,tempfile,pathlib,unittest.mock as m,json
from studio.render_worker import run_one,probe
from studio.core import Studio,CHANNEL
class RenderWorkerTests(unittest.TestCase):
 def test_idle(self):
  with tempfile.TemporaryDirectory() as d:self.assertEqual(run_one(pathlib.Path(d)/'q.sqlite',pathlib.Path(d)/'out')['state'],'idle')
 def test_unknown_recipe_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   db=pathlib.Path(d)/'q.sqlite';s=Studio(str(db));s.add('x',{'channel':CHANNEL,'recipe':'unapproved'});s.db.close()
   self.assertEqual(run_one(db,pathlib.Path(d)/'out')['state'],'failed')
 def test_probe_rejects_missing_audio(self):
  fake=type('Result',(),{'stdout':json.dumps({'streams':[{'codec_type':'video'}],'format':{'duration':'4'}})})()
  with m.patch('studio.render_worker.subprocess.run',return_value=fake):
   with self.assertRaises(ValueError):probe('fake')
