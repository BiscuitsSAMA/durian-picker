"""
🍈 榴莲图像分析模块
基于 OpenCV 做图像预处理，计算量化指标辅助 VL 模型判断。

功能：
  1. 离心率 — 评估果型圆度
  2. 刺密度 — 评估刺的密集程度
  3. 颜色分析 — 评估成熟度
"""
import cv2
import numpy as np
import math


def analyze_image(image_path):
    """
    分析榴莲图片，返回量化指标字典。
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"error": "无法读取图片", "roi_valid": False}

    h, w = img.shape[:2]
    result = {"roi_valid": False}

    # === 1. 提取榴莲主体 ===
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([15, 20, 30])
    upper = np.array([45, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        lower2 = np.array([10, 10, 20])
        upper2 = np.array([50, 255, 255])
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            mask = mask2

    if not contours:
        return {"error": "未识别到榴莲主体", "roi_valid": False}

    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < (h * w) * 0.05:
        return {"error": "榴莲区域占比过小", "roi_valid": False}

    result["roi_valid"] = True
    result["roi_area_ratio"] = round(area / (h * w), 3)

    # === 2. 离心率计算 ===
    if len(c) >= 5:
        ellipse = cv2.fitEllipse(c)
        (_, _), (major, minor), _ = ellipse
        a = max(major, minor) / 2
        b = min(major, minor) / 2
        ecc = round(math.sqrt(1 - (b**2)/(a**2)) if a > 0 else 0, 3)

        if ecc < 0.70:
            ecc_desc, ecc_score = "偏圆", 85
        elif ecc < 0.85:
            ecc_desc, ecc_score = "中等", 60
        else:
            ecc_desc, ecc_score = "偏长", 35

        result["eccentricity"] = ecc
        result["eccentricity_desc"] = ecc_desc
        result["eccentricity_score"] = ecc_score

    # === 3. 刺密度估算 ===
    contour_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(contour_mask, [c], -1, 255, -1)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_in_roi = cv2.bitwise_and(edges, edges, mask=contour_mask)

    roi_pixels = np.sum(contour_mask > 0)
    edge_pixels = np.sum(edge_in_roi > 0)
    edge_density = (edge_pixels / roi_pixels * 100) if roi_pixels > 0 else 0

    if edge_density > 10:
        spine_desc, spine_score = "密集", 80
    elif edge_density > 5:
        spine_desc, spine_score = "中等", 55
    else:
        spine_desc, spine_score = "稀疏", 30

    result["edge_density"] = round(edge_density, 2)
    result["spine_density_index"] = min(100, max(0, int(edge_density * 6)))
    result["spine_desc"] = spine_desc
    result["spine_score"] = spine_score

    # === 4. 颜色分析 ===
    roi_hsv = cv2.bitwise_and(hsv, hsv, mask=contour_mask)
    h_vals = roi_hsv[:, :, 0][contour_mask > 0]
    s_vals = roi_hsv[:, :, 1][contour_mask > 0]
    avg_h = np.mean(h_vals) if len(h_vals) > 0 else 0
    avg_s = np.mean(s_vals) if len(s_vals) > 0 else 0

    if 15 <= avg_h <= 25 and avg_s > 50:
        color_desc, color_score = "金黄/橙黄（成熟良好）", 80
    elif 25 < avg_h <= 35 and avg_s > 40:
        color_desc, color_score = "黄绿（中等成熟）", 60
    elif avg_h < 15:
        color_desc, color_score = "偏橙/棕（可能过熟）", 40
    else:
        color_desc, color_score = "偏青（未熟）", 30

    result["color"] = {
        "avg_hue": round(float(avg_h), 1),
        "avg_saturation": round(float(avg_s), 1),
        "description": color_desc,
        "score": color_score
    }

    # === 5. 综合参考分 ===
    scores = [
        result.get("eccentricity_score", 50) * 0.35,
        result.get("spine_score", 50) * 0.35,
        result["color"]["score"] * 0.30,
    ]
    result["reference_score"] = round(sum(scores), 1)
    return result


def analyze_batch(image_path):
    """批量检测图中多个榴莲，分别分析。"""
    img = cv2.imread(image_path)
    if img is None:
        return {"error": "无法读取图片"}

    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([12, 15, 25])
    upper = np.array([48, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"count": 0, "error": "未检测到榴莲"}

    min_area = (h * w) * 0.02
    valid = [c for c in contours if cv2.contourArea(c) >= min_area]
    if not valid:
        return {"count": 0, "error": "未检测到有效榴莲区域"}

    valid.sort(key=lambda c: cv2.boundingRect(c)[0])
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    results = []

    for i, c in enumerate(valid):
        label = labels[i] if i < len(labels) else f"#{i+1}"
        x, y, cw, ch = cv2.boundingRect(c)
        pad = int(min(cw, ch) * 0.1)
        roi = img[max(0, y-pad):min(h, y+ch+pad), max(0, x-pad):min(w, x+cw+pad)]

        roi_path = image_path.rsplit('.', 1)[0] + f'_{label}.png'
        cv2.imwrite(roi_path, roi)

        analysis = analyze_image(roi_path)
        results.append({"label": label, "analysis": analysis})

    results.sort(key=lambda r: r["analysis"].get("reference_score", 0), reverse=True)
    return {
        "count": len(results),
        "results": results,
        "best": results[0]["label"] if results else None,
        "best_score": results[0]["analysis"].get("reference_score", 0) if results else 0
    }
