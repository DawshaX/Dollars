"""Read-only local dashboard. Does not publish, start tasks, or expose secrets."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import sqlite3,json,html
ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/preview.mp4':
   p=ROOT/'renders/NOVA_ENGINE_TEST.mp4'
   if not p.exists():self.send_error(404,'Render not finished');return
   self.send_response(200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',str(p.stat().st_size));self.end_headers();self.wfile.write(p.read_bytes());return
  if self.path!='/':self.send_error(404);return
  db=sqlite3.connect(str(ROOT/'nova.sqlite'))
  try:rows=db.execute('SELECT state,count(*) FROM jobs GROUP BY state').fetchall()
  finally:db.close()
  p=ROOT/'renders/validation.json';validation=p.read_text() if p.exists() else 'Rendering / not yet validated'
  body='''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA Studio</title><style>body{background:#081522;color:#ebf4ff;font:18px system-ui;margin:0;padding:5vw;max-width:1000px}h1{font-size:48px;color:#7de4ce}section{padding:24px;border:1px solid #294554;border-radius:18px;margin:20px 0;background:#102332}video{max-width:100%;max-height:60vh;border-radius:12px}pre{white-space:pre-wrap;direction:ltr;text-align:left}.badge{color:#ffcf7d}</style><h1>NOVA 2099</h1><p>xDaw NoVa · لوحة هندسية تجريبية</p><section><h2>حالة التشغيل</h2><p class="badge">النشر محظور برمجيًا — لا يوجد عامل إنتاج دائم أو اتصال رفع YouTube</p><p>معرّف القناة: UCG9g_26H65D3FahqyiYPHAw</p><p>اللوحة للقراءة فقط. المعاينة اختبار للمحرك وليست الفيلم النهائي.</p></section><section><h2>معاينة اختبار الرندر</h2><video controls preload="metadata" src="/preview.mp4"></video><p>4 ثوانٍ · 360×640 · 12 إطارًا/ثانية · صوت اصطناعي بسيط. مستوى اختبار تقني، وليس مستوى الإنتاج المستهدف.</p></section><section><h2>الطابور المحلي</h2><pre>ROWS</pre></section><section><h2>التحقق التقني</h2><pre>VALIDATION</pre></section></html>'''.replace('ROWS',html.escape(json.dumps(rows,ensure_ascii=False,indent=2))).replace('VALIDATION',html.escape(validation))
  b=body.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
