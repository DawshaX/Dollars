import unittest,datetime
from studio.schedule import slots,enqueue,validate_duration
from studio.core import Studio
class ScheduleTests(unittest.TestCase):
 def setUp(self):self.t=datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc)
 def test_intervals(self):
  rows=slots(self.t,self.t,self.t+datetime.timedelta(hours=24))
  self.assertEqual(sum(r['kind']=='short' for r in rows),8)
  self.assertEqual(sum(r['kind']=='long' for r in rows),5)
 def test_no_duplicates(self):
  s=Studio(':memory:');rows=slots(self.t,self.t,self.t+datetime.timedelta(hours=1));self.assertEqual(enqueue(s,rows),2);self.assertEqual(enqueue(s,rows),0)
 def test_limits(self):
  for n in [1,60,180]:self.assertTrue(validate_duration('short',n))
  for n in [0,181,False,float('nan')]:self.assertFalse(validate_duration('short',n))
  for n in [300,1200]:self.assertTrue(validate_duration('long',n))
  for n in [299,1201]:self.assertFalse(validate_duration('long',n))
 def test_naive_rejected(self):
  with self.assertRaises(ValueError):slots(datetime.datetime(2026,1,1),self.t,self.t+datetime.timedelta(days=1))
 def test_window_no_backlog(self):
  rows=slots(self.t,self.t+datetime.timedelta(hours=23),self.t+datetime.timedelta(hours=25))
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['kind'],'short')
