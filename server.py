#!/usr/bin/env python3
"""挑个榴莲吧 — HTTP服务器"""
import os, sys, json, subprocess, uuid, io, email
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
UPLOAD = os.path.join(BASE, 'uploads')
os.makedirs(UPLOAD, exist_ok=True)

try:
    from analyzer import analyze_image_viz, analyze_batch
    ANALYZER_OK = True
except Exception as e:
    ANALYZER_OK = False

def find_models():
    try:
        r = subprocess.run(['minis-model-use','list'], capture_output=True, text=True, timeout=8)
        return [m for m in json.loads(r.stdout).get('data',{}).get('models',[]) if 'image_input' in m.get('modalities',[])]
    except:
        return []

MIME_MAP = {'html':'text/html; charset=utf-8','js':'text/javascript','css':'text/css','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    def fserve(self, path, mime):
        if not os.path.exists(path): self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Type', mime); self.end_headers()
        with open(path, 'rb') as f: self.wfile.write(f.read())

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/': self.fserve(os.path.join(BASE, 'index.html'), 'text/html; charset=utf-8')
        elif p == '/api/check':
            ms = find_models()
            self.json({'ok':len(ms)>0,'count':len(ms),'analyzer_ok':ANALYZER_OK,
                'models':[{'id':m['model_id'],'name':m['display_name'],'provider':m['instance_label']} for m in ms]})
        elif p.startswith('/uploads/'):
            self.fserve(os.path.join(UPLOAD, os.path.basename(p)), 'image/png')
        else:
            fp = os.path.join(BASE, p.lstrip('/'))
            if os.path.isfile(fp):
                ext = fp.rsplit('.',1)[-1].lower()
                self.fserve(fp, MIME_MAP.get(ext, 'text/plain'))
            else:
                self.json({'error':'not found'}, 404)

    def do_POST(self):
        if self.path != '/api/analyze': self.json({'error':'not found'}, 404); return
        ct = self.headers.get('Content-Type', '')
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        try:
            msg = email.parser.BytesParser().parsebytes(
                b'MIME-Version: 1.0\r\nContent-Type: ' + ct.encode() + b'\r\n\r\n' + raw)
        except:
            self.json({'ok':False,'error':'解析失败'}); return

        fields = {}
        if msg.is_multipart():
            for part in msg.get_payload():
                name = part.get_param('name', header='content-disposition')
                fn = part.get_filename()
                if fn:
                    fields[name] = {'filename': fn, 'content': part.get_payload(decode=True)}
                else:
                    fields[name] = part.get_payload(decode=True).decode('utf-8', errors='replace')
        else:
            self.json({'ok':False,'error':'需要 multipart'}); return

        variety = fields.get('variety', '不知道')
        sound = fields.get('sound', '没试'); pinch = fields.get('pinch', '没试')
        mode = fields.get('mode', 'single'); model_id = fields.get('model', '')
        img = fields.get('image')
        if not img: self.json({'ok':False,'error':'请上传照片'}); return
        if not model_id:
            ms = find_models()
            if not ms: self.json({'ok':False,'error':'无识图模型'}); return
            model_id = ms[0]['model_id']

        ext = img['filename'].rsplit('.',1)[-1] if '.' in img['filename'] else 'jpg'
        path = os.path.join(UPLOAD, f"{uuid.uuid4().hex}.{ext}")
        with open(path, 'wb') as f: f.write(img['content'])

        quant, viz_url = None, None
        if ANALYZER_OK:
            try:
                if mode == 'batch': quant = analyze_batch(path)
                else:
                    quant = analyze_image_viz(path)
                    if quant and quant.get('viz_path') and os.path.exists(quant['viz_path']):
                        viz_url = f"/uploads/{os.path.basename(quant['viz_path'])}"
            except: pass

        info = f"品种={variety}，声音={sound}，捏刺={pinch}"
        if quant and isinstance(quant, dict):
            if quant.get("roi_valid"):
                info += f"\n【量化】离心率={quant.get('eccentricity','N/A')}({quant.get('eccentricity_desc','')}) | 刺密度={quant.get('spine_density_index','N/A')}({quant.get('spine_desc','')}) | 颜色={quant.get('color',{}).get('description','')} | 参考分={quant.get('reference_score','N/A')}/100"
            elif "results" in quant:
                info += f"\n【批量共{quant.get('count',0)}个】"
                for r in quant.get("results",[]):
                    a = r.get("analysis",{}); info += f"\n{r['label']}: 离心率={a.get('eccentricity','N/A')} 参考分={a.get('reference_score','N/A')}"
                info += f"\n算法推荐: {quant.get('best','N/A')}"

        prompt = {"messages":[{"role":"user","content":[
            {"type":"image_url","image_url":{"url":f"file://{path}"}},
            {"type":"text","text":f"你是挑榴莲专家。{info}"}
        ]}]}
        pf = os.path.join(UPLOAD, '_p.json')
        with open(pf, 'w') as f: json.dump(prompt, f)
        try:
            r = subprocess.run(['minis-model-use','run','--model',model_id,'--input',pf], capture_output=True, text=True, timeout=30)
            resp = json.loads(r.stdout)
            text = resp.get('data',{}).get('output_text','') or resp.get('error',{}).get('message','失败')
        except subprocess.TimeoutExpired: text = '⏱️ 超时'
        except Exception as e: text = f'⚠️ {e}'
        finally:
            for f in [pf, path]:
                try: os.remove(f)
                except: pass
        self.json({'ok':True,'result':text,'viz_url':viz_url,'analyzer_ok':ANALYZER_OK})

if __name__ == '__main__':
    port = 8899
    print(f'🍈 挑个榴莲吧 → http://127.0.0.1:{port}')
    print(f'   {"✅" if ANALYZER_OK else "⚠️"} 分析模块: {"已加载" if ANALYZER_OK else "未加载"}')
    ms = find_models()
    if ms: print(f'   ✅ 识图模型: {len(ms)}个')
    else: print('   ⚠️ 无识图模型')
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()
