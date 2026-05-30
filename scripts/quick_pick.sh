#!/bin/sh
# 🍈 榴莲快速检测脚本（超市现场挑）
# ⚠️ 依赖 minis-model-use（Minis 环境），其他平台需替换为对应的 API 调用
#
# 用法: sh /var/minis/skills/durian-picker/scripts/quick_pick.sh <图片路径> [品种] [声音] [捏刺]
#
# 示例:
#   sh quick_pick.sh /var/minis/attachments/榴莲.jpg
#   sh quick_pick.sh /var/minis/attachments/榴莲.jpg 金枕头 "有撞击声" "能捏动"

IMAGE="$1"
VARIETY="${2:-未知}"
SOUND="${3:-没试}"
PINCH="${4:-没试}"

if [ -z "$IMAGE" ] || [ ! -f "$IMAGE" ]; then
    echo "❌ 用法: $0 <图片路径> [品种] [声音=没试] [捏刺=没试]"
    echo ""
    echo "📸 拍照建议：正对果柄方向，拍到果型+底部+刺"
    echo "🗣 三问："
    echo "  品种  → 金枕头/猫山王/干尧/托曼尼/黑刺/其他/不知道"
    echo "  声音  → 有撞击声/没声音/没试"
    echo "  捏刺  → 能捏动/捏不动/没试"
    exit 1
fi

echo "🍈 榴莲快检中..."
echo "📸 图片: $IMAGE"
echo "📋 品种: $VARIETY | 声音: $SOUND | 捏刺: $PINCH"
echo "---"

# 写临时JSON
JSON=$(cat << PROMPT
{
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "file://${IMAGE}"}},
        {"type": "text", "text": "你是挑榴莲专家。用户提供的额外信息：品种=${VARIETY}，摇晃声音=${SOUND}，捏刺=${PINCH}。\n\n请分析这张榴莲照片并综合信息给出结论：\n\n1️⃣ 看果型：偏圆形还是长形？底部平还是尖？\n2️⃣ 看刺：密集还是稀疏？尖还是钝？\n3️⃣ 看颜色：成熟度如何？\n4️⃣ 综合判断：\n   - 这是干包还是湿包？（干包=干爽有嚼劲，湿包=软糯水润）\n   - 熟度：熟了正好/再放1-2天/生包别买/过熟变质？\n   - 整体评分：⭐⭐⭐⭐⭐\n   - ⚡ 一句话结论（买不买？）"}
      ]
    }
  ]
}
PROMPT
)

echo "$JSON" > /tmp/quick_pick_durian.json

# 调用VL模型
minis-model-use run --model "Qwen/Qwen3-VL-8B-Instruct" --input /tmp/quick_pick_durian.json 2>/dev/null

# 清理
rm -f /tmp/quick_pick_durian.json
