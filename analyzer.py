"""
🍈 榴莲图像分析模块
依赖：Pillow + NumPy + SciPy（Alpine musl 兼容）
功能：离心率、刺密度、颜色分析 + 可视化
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from scipy import ndimage
import math, os


def _rgb_to_hsv(rgb):
    r, g, b = rgb[...,0].astype(np.float32)/255.0, rgb[...,1].astype(np.float32)/255.0, rgb[...,2].astype(np.float32)/255.0
    cmax, cmin = np.maximum(r, np.maximum(g,b)), np.minimum(r, np.minimum(g,b))
    delta = cmax - cmin + 1e-10
    h = np.zeros_like(cmax, dtype=np.float32)
    mr, mg, mb = (cmax==r), (cmax==g), (cmax==b)
    h[mr] = (60*((g[mr]-b[mr])/delta[mr])+360)%360
    h[mg] = 60*((b[mg]-r[mg])/delta[mg])+120
    h[mb] = 60*((r[mb]-g[mb])/delta[mb])+240
    s = np.where(cmax==0, 0.0, delta/cmax*255.0).astype(np.float32)
    v = (cmax*255.0).astype(np.float32)
    return np.stack([h,s,v], axis=-1)

def _find_largest_contour(mask):
    labeled, n = ndimage.label(mask)
    if n==0: return None
    sizes = ndimage.sum(mask, labeled, range(1, n+1))
    return (labeled==(np.argmax(sizes)+1)).astype(np.uint8)

def _contour_area(b): return np.sum(b>0)

def _ellipse_from_moment(binary):
    ys, xs = np.where(binary>0)
    if len(xs)<5: return None
    xm, ym = np.mean(xs), np.mean(ys)
    uxx, uyy = np.mean((xs-xm)**2), np.mean((ys-ym)**2)
    uxy = np.mean((xs-xm)*(ys-ym))
    c = math.sqrt((uxx-uyy)**2+4*uxy**2)
    l1, l2 = (uxx+uyy+c)/2, (uxx+uyy-c)/2
    if l1<=0 or l2<=0: return None
    a, b = math.sqrt(l1)*2, math.sqrt(l2)*2
    if a<=0: return None
    ecc = math.sqrt(1-(b**2)/(a**2)) if a>b else 0
    return ecc, a, b, xm, ym


def analyze_image(image_path):
    """分析单张榴莲图片，返回量化指标"""
    try:
        pil_img = Image.open(image_path).convert('RGB')
    except:
        return {"error": "无法读取图片", "roi_valid": False}

    w, h = pil_img.size
    if max(w,h)>800:
        s = 800.0/max(w,h); pil_img = pil_img.resize((int(w*s),int(h*s)))
        w, h = pil_img.size
    arr = np.array(pil_img); result = {"roi_valid": False}

    hsv = _rgb_to_hsv(arr)
    mask = ((hsv[...,0]>=12)&(hsv[...,0]<=50)&(hsv[...,1]>=15)&(hsv[...,2]>=25)).astype(np.uint8)
    mask = ndimage.binary_closing(mask, np.ones((5,5)), iterations=2).astype(np.uint8)
    mask = ndimage.binary_opening(mask, np.ones((3,3)), iterations=1).astype(np.uint8)
    binary = _find_largest_contour(mask)
    if binary is None or _contour_area(binary)<(w*h)*0.03:
        return {"error":"未识别到榴莲主体", "roi_valid":False}
    result["roi_valid"]=True; result["roi_area_ratio"]=round(_contour_area(binary)/(w*h),3)

    ellipse = _ellipse_from_moment(binary)
    if ellipse:
        ecc,a,b,cx,cy = ellipse; ecc = round(ecc,3)
        if ecc<0.70: ed,es = "偏圆",85
        elif ecc<0.85: ed,es = "中等",60
        else: ed,es = "偏长",35
        result["eccentricity"]=ecc; result["eccentricity_desc"]=ed; result["eccentricity_score"]=es
        result["ellipse"]={"cx":float(cx),"cy":float(cy),"a":float(a),"b":float(b)}

    gray = np.mean(arr,axis=2).astype(np.float64)
    sx = ndimage.sobel(gray,1); sy = ndimage.sobel(gray,0)
    edges = np.hypot(sx,sy)>40
    edge_roi = edges&(binary>0)
    rp, ep = np.sum(binary>0), np.sum(edge_roi)
    edens = (ep/rp*100) if rp>0 else 0
    if edens>8: sd,ss = "密集",80
    elif edens>4: sd,ss = "中等",55
    else: sd,ss = "稀疏",30
    result["edge_density"]=round(edens,2); result["spine_density_index"]=min(100,max(0,int(edens*8)))
    result["spine_desc"]=sd; result["spine_score"]=ss

    h_vals = hsv[...,0][binary>0]; s_vals = hsv[...,1][binary>0]
    ah, asat = float(np.mean(h_vals)), float(np.mean(s_vals))
    if 15<=ah<=25 and asat>40: cd,cs = "金黄/橙黄（成熟良好）",80
    elif 25<ah<=38: cd,cs = "黄绿（中等成熟）",55
    elif ah<15: cd,cs = "偏橙/棕（可能过熟）",40
    else: cd,cs = "偏青（未熟）",30
    result["color"]={"avg_hue":round(ah,1),"avg_saturation":round(asat,1),"description":cd,"score":cs}

    rscore = round(sum([result.get("eccentricity_score",50)*0.35,result.get("spine_score",50)*0.35,result["color"]["score"]*0.30]),1)
    result["reference_score"] = rscore

    result["_img"] = pil_img; result["_binary"] = binary
    result["_edges"] = edges; result["_edge_roi"] = edge_roi
    return result


def generate_viz(result, image_path):
    """生成分析过程可视化图"""
    if not result.get("roi_valid"): return None
    pil_img, binary = result.get("_img"), result.get("_binary")
    edges, edge_roi = result.get("_edges"), result.get("_edge_roi")
    if pil_img is None or binary is None: return None

    w, h = pil_img.size; pw, ph = 500, 375
    canvas = Image.new('RGB', (pw*2, ph*2), (245,245,247))
    draw = ImageDraw.Draw(canvas)
    try:
        ft = ImageFont.truetype("/usr/share/fonts/noto/NotoSansCJK-Regular.ttc", 18)
        fs = ImageFont.truetype("/usr/share/fonts/noto/NotoSansCJK-Regular.ttc", 14)
        fxs = ImageFont.truetype("/usr/share/fonts/noto/NotoSansCJK-Regular.ttc", 12)
    except:
        ft = fs = fxs = ImageFont.load_default()

    def paste_at(panel, img):
        cw, ch = pw-4, ph-4
        if img.size[0]>cw or img.size[1]>ch: img.thumbnail((cw,ch), Image.LANCZOS)
        canvas.paste(img, (panel[0]*pw+2, panel[1]*ph+2))

    paste_at((0,0), pil_img)
    draw.text((10,6), "📸 原图", fill="#1d1d1f", font=fs)

    # 轮廓覆盖
    ov = pil_img.copy().convert('RGBA'); oa = np.array(ov)
    # 确保binary与oa的2D尺寸一致（PIL size=宽x高 vs numpy shape=高x宽）
    if oa.shape[0] != binary.shape[0] or oa.shape[1] != binary.shape[1]:
        from PIL import Image as _IR
        binary = np.array(_IR.fromarray(binary.astype(np.uint8)*255).resize((oa.shape[1], oa.shape[0]), _IR.NEAREST)) > 0
    oa[binary>0] = (oa[binary>0]*0.6 + np.array([0,122,255,100])*0.4).astype(np.uint8)
    ce = ndimage.binary_dilation(binary, iterations=2).astype(np.uint8) - binary
    oa[ce>0] = [0,122,255,255]

    ell = result.get("ellipse")
    if ell:
        cx, cy, ea, eb = ell["cx"], ell["cy"], ell["a"], ell["b"]
        ov2 = Image.fromarray(oa); d2 = ImageDraw.Draw(ov2)
        d2.ellipse([cx-ea, cy-eb, cx+ea, cy+eb], outline="#ff3b30", width=3)
        d2.text((cx+5, cy-20), f'离心率={result.get("eccentricity","?")} {result.get("eccentricity_desc","")}', fill="#ff3b30", font=fxs)
        paste_at((1,0), ov2.convert('RGB'))
    else:
        paste_at((1,0), Image.fromarray(oa).convert('RGB'))
    draw.text((pw+10,6), "🎯 轮廓+椭圆拟合", fill="#1d1d1f", font=fs)

    # 边缘图
    ev = (edges.astype(np.uint8)*255)
    paste_at((0,1), Image.fromarray(ev, mode='L').convert('RGB'))
    draw.text((10,ph+6), f"🌵 边缘·刺密度={result.get('spine_density_index','?')}({result.get('spine_desc','')})", fill="#1d1d1f", font=fs)

    erv = (edge_roi.astype(np.uint8)*255)
    paste_at((1,1), Image.fromarray(erv, mode='L').convert('RGB'))
    draw.text((pw+10,ph+6), f"📐 ROI·{result.get('edge_density','?')}%", fill="#1d1d1f", font=fs)

    # 底部评分条
    score = result.get("reference_score", 0)
    sc = "#34c759" if score>=70 else ("#f59e0b" if score>=50 else "#ff3b30")
    draw.rectangle([0, ph*2-36, pw*2, ph*2], fill="#1d1d1f")
    draw.text((20, ph*2-30), f"综合参考分: {score}/100", fill=sc, font=ft)
    bx, bw = 240, 240
    draw.rectangle([bx, ph*2-26, bx+bw, ph*2-12], fill="#3a3a3c")
    draw.rectangle([bx, ph*2-26, bx+int(bw*score/100), ph*2-12], fill=sc)

    viz_path = image_path.rsplit('.',1)[0]+'_viz.png'
    canvas.save(viz_path, quality=92)
    return viz_path


def analyze_image_viz(image_path):
    """分析+可视化一站式"""
    result = analyze_image(image_path)
    if result.get("roi_valid"):
        viz = generate_viz(result, image_path)
        if viz: result["viz_path"] = viz
    for k in ["_img","_binary","_edges","_edge_roi","ellipse"]:
        result.pop(k, None)
    return result


def analyze_batch(image_path):
    """批量检测多个榴莲"""
    pil_img = Image.open(image_path).convert('RGB')
    w, h = pil_img.size
    if max(w,h)>1000:
        s = 1000.0/max(w,h); pil_img = pil_img.resize((int(w*s),int(h*s)))
        w, h = pil_img.size
    arr = np.array(pil_img); hsv = _rgb_to_hsv(arr)
    mask = ((hsv[...,0]>=12)&(hsv[...,0]<=50)&(hsv[...,1]>=15)&(hsv[...,2]>=25)).astype(np.uint8)
    mask = ndimage.binary_closing(mask, np.ones((5,5)), iterations=2).astype(np.uint8)
    mask = ndimage.binary_opening(mask, np.ones((3,3)), iterations=1).astype(np.uint8)
    labeled, n = ndimage.label(mask)
    if n==0: return {"count":0,"error":"未检测到榴莲"}
    min_a = (w*h)*0.015; results=[]; L="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(1,n+1):
        comp = (labeled==i).astype(np.uint8)
        if np.sum(comp>0)<min_a: continue
        ys,xs = np.where(comp>0)
        y1,y2,x1,x2 = max(0,ys.min()-5),min(h,ys.max()+5),max(0,xs.min()-5),min(w,xs.max()+5)
        roi = arr[y1:y2,x1:x2]
        idx = len(results); lb = L[idx] if idx<len(L) else f"#{idx+1}"
        rp = image_path.rsplit('.',1)[0]+f'_{lb}.png'
        Image.fromarray(roi).save(rp)
        a = analyze_image_viz(rp)
        results.append({"label":lb,"analysis":a})
    results.sort(key=lambda r:r["analysis"].get("reference_score",0), reverse=True)
    return {"count":len(results),"results":results,"best":results[0]["label"] if results else None,
            "best_score":results[0]["analysis"].get("reference_score",0) if results else 0}
