#!/bin/sh
# 🍈 挑个榴莲吧 · 一键安装
set -e
echo ""
echo "🍈 挑个榴莲吧 — 一键安装"
echo "=========================="
echo ""

echo "📦 安装 py3-numpy..."
apk add --no-cache py3-numpy 2>&1 | tail -1

echo "📦 安装 py3-scipy..."
apk add --no-cache py3-scipy 2>&1 | tail -1

echo "📦 安装 py3-opencv..."
apk add --no-cache py3-opencv 2>&1 | tail -1

echo ""
echo "🔍 验证..."
python3 -c "
import cv2; print(f'✅ OpenCV {cv2.__version__}')
import numpy; print(f'✅ NumPy {numpy.__version__}')
import analyzer; print(f'✅ analyzer 模块就绪')
"

mkdir -p uploads

echo ""
echo "🎉 安装完成！启动服务："
echo "   nohup python3 server.py > /tmp/durian_server.log 2>&1 &"
echo "   打开 http://127.0.0.1:8899/"
