import unittest,unittest.mock as m,os
from studio.youtube_upload import verify_channel,upload,validate
from studio.core import CHANNEL
class UploadTests(unittest.TestCase):
 def test_wrong_destination(self):
  with m.patch('studio.youtube_upload.request_json',return_value={'items':[{'id':'other'}]}):
   with self.assertRaises(RuntimeError):verify_channel('fake')
 def test_correct_destination(self):
  with m.patch('studio.youtube_upload.request_json',return_value={'items':[{'id':CHANNEL}]}):self.assertEqual(verify_channel('fake'),CHANNEL)
 def test_activation_closed(self):
  with m.patch.dict(os.environ,{'NOVA_ENABLE_UPLOAD':'0'}):
   with self.assertRaises(RuntimeError):upload('none',{})
 def test_test_artifact_rejected(self):
  with self.assertRaises(ValueError):validate('none',{'channel':CHANNEL,'engine_test':True})
 def test_missing_review(self):
  with self.assertRaises(ValueError):validate('none',{'channel':CHANNEL,'engine_test':False})
