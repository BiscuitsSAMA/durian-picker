# 🍈 挑个榴莲吧

AI 榴莲挑选专家——拍照上传，30 秒告诉你这颗榴莲值不值得买。

支持 Claude、Codex、OpenClaw / Minis 等 Agent 加载使用，也提供独立 Web 页面。

---

## 🚀 快速开始（Web 页面）

```bash
# 1. 克隆项目
git clone https://github.com/BiscuitsSAMA/durian-picker.git
cd durian-picker

# 2. 一键安装依赖
sh setup.sh

# 3. 启动服务
nohup python3 server.py > /tmp/durian_server.log 2>&1 &

# 4. 浏览器打开
#    http://127.0.0.1:8899/
```

然后拍照上传 + 选择品种/声音/捏刺 → AI 分析 → 出结论 + 可视化图表。

---

## 🧠 算法说明

本项目的分析分两层：**图像量化分析** + **多模态大模型判断**，双重验证。

### 1️⃣ 图像量化分析（analyzer.py）

| 算法 | 实现方式 | 用途 |
|------|---------|------|
| **HSV 颜色分割** | RGB→HSV 转换 + 阈值掩码 | 从背景中提取榴莲主体 |
| **连通域分析** | SciPy ndimage.label | 找最大连通域作为榴莲轮廓 |
| **离心率计算** | 图像矩 → 协方差矩阵 → 椭圆拟合 | 量化果型圆度（<0.7偏圆，>0.85偏长） |
| **Sobel 边缘检测** | SciPy ndimage.sobel | 检测榴莲表面刺的密集程度 |
| **HSV 颜色分析** | 平均色调 + 饱和度 | 评估成熟度（金黄=成熟，偏青=未熟） |

**依赖**：Python 3、Pillow、NumPy、SciPy（无需 OpenCV，兼容 Alpine musl）

### 2️⃣ 多模态大模型判断

图像量化数据作为 **extra 信息** 喂给 VL 模型，辅助视觉判断：

| 模型 | 来源 | 用途 |
|------|------|------|
| **Qwen3-VL-8B-Instruct** | 阿里通义千问 / 硅基流动 | 🔸 默认模型，快速分析 |
| Qwen3-VL-32B-Instruct | 阿里通义千问 / 硅基流动 | 更细致的分析（可选） |
| Kimi K2.6 | Moonshot AI / 硅基流动 | 备选模型 |
| GPT-5.5 | OpenAI | 备选模型 |

> 所有模型均通过 `minis-model-use` 调用，由 **硅基流动 (SiliconFlow)** 提供 API。

### 3️⃣ 判别机制

```
用户上传图片
   ↓
analyzer.py 图像量化
   ├── 离心率 → 果型圆度
   ├── 边缘密度 → 刺密集程度
   └── HSV颜色 → 成熟度
   ↓
量化数据 + 原图 → VL 模型综合判断
   ↓
输出结论：干包/湿包/生包 + 熟度 + 评分 + 建议
```

### 4️⃣ 可视化（2×2 四格图）

分析结果附带可视化图，直观展示处理过程：
- 左上：原图
- 右上：轮廓 + 椭圆拟合（带离心率标注）
- 左下：Sobel 边缘检测（刺密度）
- 右下：ROI 区域边缘（量化百分比）
- 底部：综合参考评分条

---

## 📖 SKILL 模式（Agent 加载）

Claude、Codex、OpenClaw / Minis 等 Agent 可直接加载 `SKILL.md`：

```
durian-picker/
├── SKILL.md       ← 核心知识库 + 工作流（Agent 加载这个）
├── server.py      ← Web 服务器
├── index.html     ← 前端页面
├── analyzer.py    ← 图像量化分析
├── setup.sh       ← 一键安装
└── scripts/
```

Agent 加载后自动支持两种模式：

| 模式 | 触发方式 | 流程 |
|------|---------|------|
| 🏪 **批量挑** 🔜 | "帮我从这堆榴莲里挑一个" | 开发中，敬请期待 |
| 🔍 **单果鉴定** | "看看这个榴莲怎么样" | 问三问 → 多模态看图 → 干包/湿包判断 |

---

## 🔧 配置说明

### 前置要求
- **Python 3.10+**
- **minis-model-use**（Minis 环境）或其他兼容的 LLM 调用工具
- **硅基流动 (SiliconFlow) API Key** 或其他支持图像识别的 LLM 提供商

### 首次安装
```bash
sh setup.sh
```
自动安装：Pillow、NumPy、SciPy

### 如果需要更换模型

编辑 `server.py`，在 `find_models()` 的返回列表中指定你想要的模型 ID，或在页面上的模型选择下拉框中切换。

---

## 🔗 参考项目

- [thinksoso/pick_your_durian](https://github.com/thinksoso/pick_your_durian) — SAM 分割 → 离心率 + 刺密度评估（启发本项目的量化算法）
- [liujiaqi222/durian-helper-mini-program](https://github.com/liujiaqi222/durian-helper-mini-program) — YOLO 检测 + 多模态评分（启发批量编号逻辑）

---

## 🍈 品种速查

| 品种 | 特征 |
|------|------|
| 金枕头🥇 | 金黄、会裂口、甜糯、新手友好 |
| 猫山王👑 | 黄绿、不裂需刀开、苦甜浓郁 |
| 黑刺🖤 | 偏绿不裂、奶油质地、顶级 |
| 干尧🫒 | 青绿、微裂、细腻高甜 |
| 托曼尼🟢 | 偏绿不裂、似猫山王籽大 |

## 四句口诀

> **圆胖鼓包刺能捏，轻摇有响香味浓**
> **微开新鲜柄湿润，皮薄肉多不踩雷**

---

## License

MIT
