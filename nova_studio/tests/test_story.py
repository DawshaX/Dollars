import unittest,sqlite3
from studio.story import WorldMemory
from studio.core import CHANNEL
class StoryTests(unittest.TestCase):
 def setUp(self):self.m=WorldMemory(':memory:')
 def tearDown(self):self.m.close()
 def test_planning_does_not_change_world(self):
  _,p=self.m.plan('lost_sun');self.assertFalse(self.m.state()['sun_repaired']);self.assertEqual(p['duration_seconds'],24)
 def test_no_duplicate(self):
  self.m.plan('lost_sun')
  with self.assertRaises(sqlite3.IntegrityError):self.m.plan('lost_sun')
 def test_prerequisite(self):
  with self.assertRaises(ValueError):self.m.plan('quiet_canal')
 def test_confirm_continuity(self):
  fp,_=self.m.plan('lost_sun');self.m.confirm_publication(fp,'abcdefghijk',CHANNEL);self.assertTrue(self.m.state()['sun_repaired']);self.m.plan('quiet_canal')
 def test_wrong_channel(self):
  fp,_=self.m.plan('lost_sun')
  with self.assertRaises(ValueError):self.m.confirm_publication(fp,'abcdefghijk','other')
  self.assertFalse(self.m.state()['sun_repaired'])
 def test_no_long_padding(self):
  with self.assertRaises(ValueError):self.m.plan('lost_sun','long')
