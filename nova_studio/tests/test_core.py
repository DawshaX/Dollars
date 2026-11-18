import unittest,sqlite3,time
from studio.core import Studio,CHANNEL,quality,publish
class Tests(unittest.TestCase):
 def setUp(self):self.s=Studio(':memory:')
 def test_channel(self):
  with self.assertRaises(ValueError):self.s.add('x',{'channel':'other'})
 def test_unique(self):
  self.s.add('x',{'channel':CHANNEL})
  with self.assertRaises(sqlite3.IntegrityError):self.s.add('x',{'channel':CHANNEL})
 def test_claim(self):
  i=self.s.add('x',{'channel':CHANNEL});self.assertEqual(self.s.claim()[0],i);self.assertIsNone(self.s.claim());self.s.finish(i,'review');self.assertEqual(self.s.status(),[('review',1)])
 def test_recovery(self):
  self.s.add('x',{'channel':CHANNEL});self.s.claim();self.s.db.execute('UPDATE jobs SET lease=0');self.s.db.commit();self.assertIsNotNone(self.s.claim())
 def test_quality(self):self.assertTrue(quality({'channel':CHANNEL}))
 def test_publish_blocked(self):
  with self.assertRaises(RuntimeError):publish()
if __name__=='__main__':unittest.main()
