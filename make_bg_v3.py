#!/usr/bin/env python3
"""元神AI背景图v3 - PIL高效绘制版"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
import os, random, math
from PIL import Image, ImageDraw, ImageFilter, ImageChops

random.seed(42)
W, H = 3840, 2160

# ─── 通用工具 ───────────────────────────────
def blend_onto(base, overlay, alpha=0.5):
    """叠加overlay到底图base"""
    tmp = Image.new('RGB', base.size, (0,0,0))
    tmp.paste(overlay, (0,0))
    return Image.blend(base, tmp, alpha)

def glow_layer(w, h, cx, cy, rx, ry, color, blur=30):
    """创建椭圆形发光层"""
    layer = Image.new('RGB', (w, h), (0,0,0))
    d = ImageDraw.Draw(layer)
    for r in range(max(int(min(rx,ry)*0.3), 1), 0, -1):
        t = r / max(rx, ry, 1)
        a = int(255 * (t ** 0.8))
        layer_px = (min(255, color[0]+a//3),
                     min(255, color[1]+a//3),
                     min(255, color[2]+a//4))
        d.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=layer_px)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return layer

# ═══════════════════════════════════════════
# 背景一：封面/封底
# 深邃宇宙 + 星云暗纹 + 底部柔和鎏金光芒
# 关键词：光芒柔和内敛，不抢主体，居中汇聚感
# ═══════════════════════════════════════════
def make_bg1():
    print("背景一（封面封底）...", flush=True)
    t0 = os.times().elapsed

    # 底层
    img = Image.new('RGB', (W, H), (2, 4, 12))

    # 星云：多个模糊椭圆
    nebula = Image.new('RGB', (W, H), (0,0,0))
    nd = ImageDraw.Draw(nebula)
    for cx, cy, rw, rh, col in [
        (W//3, H//3, W//3, H//3, (20,8,42)),
        (W*2//3, H//2, W//4, H//2, (12,6,30)),
        (W//2, H*2//3, W//3, H//3, (26,13,52)),
        (W*3//4, H//4, W//5, H//3, (10,5,24)),
        (W//6, H*3//4, W//4, H//3, (16,9,40)),
        (W//2, H//4, W//4, H//4, (8,4,20)),
    ]:
        nd.ellipse([cx-rw, cy-rh, cx+rw, cy+rh], fill=col)
    nebula = nebula.filter(ImageFilter.GaussianBlur(110))
    img = Image.blend(img, nebula, 0.75)

    # 星光
    stars = Image.new('L', (W//4, H//4), 0)
    sd = ImageDraw.Draw(stars)
    for _ in range(4000):
        sx = random.randint(0, W//4-1)
        sy = random.randint(0, H//4-1)
        b = random.randint(80, 255)
        sz = random.choice([1,1,2])
        sd.ellipse([sx,sy,sx+sz,sy+sz], fill=b)
    stars = stars.filter(ImageFilter.GaussianBlur(1)).resize((W, H), Image.LANCZOS)
    stars_rgb = Image.merge('RGB', [stars,stars,stars])
    img = Image.blend(img, stars_rgb, 0.42)

    # 底部柔和鎏金光芒
    # 中心垂直光带 + 两侧衰减
    glow_bar = Image.new('RGB', (W, H), (0,0,0))
    gd = ImageDraw.Draw(glow_bar)
    glow_h = H * 2 // 5  # 光芒总高度（底部40%）
    glow_top_y = H - glow_h
    center_x = W // 2
    half_width = W * 3 // 10  # 光带半宽

    for y in range(glow_h):
        t = y / glow_h  # 0=底部, 1=顶部
        base_alpha = 0.55 * (1 - t ** 0.7)
        for x in range(W):
            dx = abs(x - center_x)
            if dx <= half_width:
                dist = dx / half_width
                att = (1 - dist ** 1.5) * base_alpha
                gold = (185 + int(25*att), 148 + int(18*att), int(8*att))
                gd.point((x, glow_top_y + y), fill=gold)
    glow_bar = glow_bar.filter(ImageFilter.GaussianBlur(50))
    img = Image.blend(img, glow_bar, 0.6)

    # 底部中心汇聚光点（极柔和）
    center_dot = glow_layer(W, H, W//2, H-40, 80, 40, (200, 165, 20), blur=35)
    img = Image.blend(img, center_dot, 0.55)

    out = "/Users/w/.openclaw/workspace/bg1_封面封底.png"
    img.save(out, optimize=True)
    img720 = img.resize((1280, 720), Image.LANCZOS)
    img720.save("/Users/w/.openclaw/workspace/bg1_1280.png", 'PNG')
    sz = os.path.getsize(out)
    print(f"✅ 背景一完成 {sz//1024}KB ({os.times().elapsed-t0:.1f}s)", flush=True)

# ═══════════════════════════════════════════
# 背景二：目录页
# 黑金奢雅 + 左下→右上鎏金线条汇聚
# ═══════════════════════════════════════════
def make_bg2():
    print("背景二（目录页）...", flush=True)
    t0 = os.times().elapsed

    img = Image.new('RGB', (W, H), (4, 5, 15))

    # 汇聚线条
    lines = Image.new('RGB', (W, H), (0,0,0))
    ld = ImageDraw.Draw(lines)
    sx, sy = W//8, int(H*0.88)
    ex, ey = int(W*0.6), int(H*0.36)
    dx, dy = ex-sx, ey-sy
    L = math.sqrt(dx**2+dy**2)
    nx, ny = -dy/L, dx/L

    for i in range(28):
        off = (i-14)*18
        osx = sx + nx*off; osy = sy + ny*off
        oex = ex + nx*off*0.4; oey = ey + ny*off*0.4
        inten = max(30, 200 - abs(i-14)*6)
        col = (min(255,165+inten//4), min(255,125+inten//5), 0)
        w_l = max(1, 4 - abs(i-14)//20)
        ld.line([(int(osx),int(osy)), (int(oex),int(oey))], fill=col, width=w_l)

    lines = lines.filter(ImageFilter.GaussianBlur(10))
    img = Image.blend(img, lines, 0.85)

    # 汇聚点光晕
    glow_pt = glow_layer(W, H, int(W*0.58), int(H*0.38), 90, 45, (210, 170, 15), blur=18)
    img = Image.blend(img, glow_pt, 0.7)

    # 星点
    stars = Image.new('L', (W//3, H//3), 0)
    sd = ImageDraw.Draw(stars)
    for _ in range(1200):
        sx2 = random.randint(0, W//3-1)
        sy2 = random.randint(0, H//3-1)
        b = random.randint(60, 210)
        sd.point((sx2, sy2), fill=b)
    stars = stars.filter(ImageFilter.GaussianBlur(1)).resize((W, H), Image.LANCZOS)
    stars_rgb = Image.merge('RGB', [stars,stars,stars])
    img = Image.blend(img, stars_rgb, 0.28)

    out = "/Users/w/.openclaw/workspace/bg2_目录页.png"
    img.save(out, optimize=True)
    img720 = img.resize((960, 540), Image.LANCZOS)
    img720.save("/Users/w/.openclaw/workspace/bg2_1280.png", 'PNG')
    sz = os.path.getsize(out)
    print(f"✅ 背景二完成 {sz//1024}KB ({os.times().elapsed-t0:.1f}s)", flush=True)

# ═══════════════════════════════════════════
# 背景三：内容页
# 深黑微蓝纹理 + 边缘鎏金细线 + 四角L型装饰
# ═══════════════════════════════════════════
def make_bg3():
    print("背景三（内容页）...", flush=True)
    t0 = os.times().elapsed

    img = Image.new('RGB', (W, H), (3, 6, 16))

    # 深蓝纹理
    tex = Image.new('RGB', (W, H), (0,0,0))
    td = ImageDraw.Draw(tex)
    for _ in range(15):
        cx = random.randint(0, W); cy = random.randint(0, H)
        rw = random.randint(W//7, W//2); rh = random.randint(H//7, H//2)
        td.ellipse([cx-rw,cy-rh,cx+rw,cy+rh],
                   fill=(random.randint(5,20), random.randint(8,30), random.randint(25,58)))
    tex = tex.filter(ImageFilter.GaussianBlur(140))
    img = Image.blend(img, tex, 0.6)

    # 边缘金色渐变线
    edge = Image.new('RGB', (W, H), (0,0,0))
    ed = ImageDraw.Draw(edge)
    M = 80
    for i in range(M):
        t = (M-i)/M
        a = int(165*t)
        col = (min(255,180+a//4), min(255,140+a//5), 0)
        w = max(1, 3-i//25)
        # 顶边
        ed.line([(0,i),(W,i)], fill=col, width=w)
        # 底边
        ed.line([(0,H-1-i),(W,H-1-i)], fill=col, width=w)
        # 左边
        ed.line([(i,0),(i,H)], fill=col, width=w)
        # 右边
        ed.line([(W-1-i,0),(W-1-i,H)], fill=col, width=w)
    edge = edge.filter(ImageFilter.GaussianBlur(5))
    img = Image.blend(img, edge, 0.9)

    # 四角L型装饰
    corner = Image.new('RGB', (W, H), (0,0,0))
    cd = ImageDraw.Draw(corner)
    CL = 140
    for (x0, y0, dx, dy) in [(0,0,1,1),(W-1,0,-1,1),(0,H-1,1,-1),(W-1,H-1,-1,-1)]:
        for i in range(CL):
            t = i/CL
            a = int(190*(1-t**0.7))
            col = (min(255,188+a//4), min(255,148+a//5), 0)
            w = max(1, 2-i//70)
            if dx > 0:
                xs, xe = x0, x0+int(CL*t)
            else:
                xs, xe = x0+int(CL*t), x0
            if dy > 0:
                ys, ye = y0, y0+int(CL*t)
            else:
                ys, ye = y0+int(CL*t), y0
            cd.line([(xs,y0),(xe,y0)], fill=col, width=w)
            cd.line([(x0,ys),(x0,ye)], fill=col, width=w)
    corner = corner.filter(ImageFilter.GaussianBlur(3))
    img = Image.blend(img, corner, 1.0)

    out = "/Users/w/.openclaw/workspace/bg3_内容页.png"
    img.save(out, optimize=True)
    img720 = img.resize((1280, 720), Image.LANCZOS)
    img720.save("/Users/w/.openclaw/workspace/bg3_1280.png", 'PNG')
    sz = os.path.getsize(out)
    print(f"✅ 背景三完成 {sz//1024}KB ({os.times().elapsed-t0:.1f}s)", flush=True)

if __name__ == "__main__":
    import time
    t0 = time.time()
    make_bg1()
    make_bg2()
    make_bg3()
    print(f"\n✅ 全部完成，耗时 {time.time()-t0:.1f}s")
