#!/usr/bin/env python3
"""
🍈 挑个榴莲吧 - 本地分析服务器（Minis 增强版）

启动方式：
    nohup python3 server.py > /tmp/durian_server.log 2>&1 &

然后浏览器打开 http://127.0.0.1:8899/
"""
import os, json, subprocess, uuid
from flask import Flask, request, jsonify, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(BASE, 'uploads')
os.makedirs(UPLOAD, exist_ok=True)

app = Flask(__name__, static_folder=None)


def find_vision_models():
    """检测可用的图像识别模型"""
    try:
        r = subprocess.run(['minis-model-use', 'list'], capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        models = data.get('data', {}).get('models', [])
        return [m for m in models if 'image_input' in m.get('modalities', [])]
    except:
        return []


@app.route('/')
def index():
    return send_from_directory(BASE, 'index.html')


@app.route('/<path:p>')
def sf(p):
    return send_from_directory(BASE, p)


@app.route('/api/check')
def api_check():
    """检测是否有可用识图模型"""
    models = find_vision_models()
    return jsonify({
        'ok': len(models) > 0,
        'models': [{'id': m['model_id'], 'name': m['display_name'], 'provider': m['instance_label']} for m in models],
        'count': len(models)
    })


@app.route('/api/analyze', methods=['POST'])
def analyze():
    variety = request.form.get('variety', '不知道')
    sound = request.form.get('sound', '没试')
    pinch = request.form.get('pinch', '没试')
    model_id = request.form.get('model', '')
    img = request.files.get('image')

    if not img:
        return jsonify({'ok': False, 'error': '请上传照片'})

    # 自动选第一个可用模型
    if not model_id:
        models = find_vision_models()
        if not models:
            return jsonify({'ok': False, 'error': '没有可用的识图模型，请先配置 Provider'})
        model_id = models[0]['model_id']

    ext = img.filename.rsplit('.', 1)[-1] if '.' in img.filename else 'jpg'
    path = os.path.join(UPLOAD, f"{uuid.uuid4().hex}.{ext}")
    img.save(path)

    prompt = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"file://{path}"}},
                {"type": "text", "text": f"用户信息：品种={variety}，声音={sound}，捏刺={pinch}。请分析这张榴莲照片：1)果型偏圆还是长？底平还是尖？2)刺密集还是稀疏？尖还是钝？3)颜色成熟度？4)综合判断：干包/湿包/生包？熟度？评分1-5星？一句话买不买？"}
            ]
        }]
    }

    pf = os.path.join(UPLOAD, '_p.json')
    with open(pf, 'w') as f:
        json.dump(prompt, f)

    try:
        r = subprocess.run(
            ['minis-model-use', 'run', '--model', model_id, '--input', pf],
            capture_output=True, text=True, timeout=30
        )
        resp = json.loads(r.stdout)
        text = resp.get('data', {}).get('output_text', '')
        if not text:
            err = resp.get('error', {})
            text = err.get('message', '分析失败')
    except subprocess.TimeoutExpired:
        text = '⏱️ 分析超时，请重试'
    except Exception as e:
        text = f'⚠️ 系统错误: {e}'
    finally:
        for f in [pf, path]:
            try: os.remove(f)
            except: pass

    return jsonify({'ok': True, 'result': text})


if __name__ == '__main__':
    print('🍈 挑个榴莲吧 · 服务器启动 → http://127.0.0.1:8899')
    models = find_vision_models()
    if models:
        print(f'   ✅ 检测到 {len(models)} 个识图模型，可用')
    else:
        print('   ⚠️ 未检测到识图模型，请先在 Settings → Providers 配置')
    app.run(host='127.0.0.1', port=8899, debug=False)
