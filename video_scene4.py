#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-
"""第四幕《普通人与元神的一天》分镜故事板 + HTML动画生成器"""
import sys; sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os
from pathlib import Path

OUT = Path("/Users/w/.openclaw/workspace/video_scene4")
OUT.mkdir(exist_ok=True)

W, H = 1920, 817   # 2.35:1
COLD = (26, 38, 58)
WARM = (18, 12, 5)
WHITE = (248, 250, 252)
GOLD = (212, 175, 55)
GRAY = (148, 163, 184)
BLUE_ACCENT = (33, 150, 243)
CARD = (15, 25, 45)

def gradient(draw, x1, y1, x2, y2, c1, c2):
    """线性渐变填充"""
    if x1 == x2:
        for y in range(y1, y2+1):
            t = (y-y1)/(y2-y1) if y2>y1 else 0
            r = int(c1[0]*(1-t)+c2[0]*t)
            g = int(c1[1]*(1-t)+c2[1]*t)
            b = int(c1[2]*(1-t)+c2[2]*t)
            draw.line([(x1,y),(x2,y)], fill=(r,g,b))
    else:
        for x in range(x1, x2+1):
            t = (x-x1)/(x2-x1) if x2>x1 else 0
            r = int(c1[0]*(1-t)+c2[0]*t)
            g = int(c1[1]*(1-t)+c2[1]*t)
            b = int(c1[2]*(1-t)+c2[2]*t)
            draw.line([(x,y1),(x,y2)], fill=(r,g,b))

def get_font(size, bold=False):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc" if bold else
                                   "/System/Library/Fonts/Hiragino Sans GB.ttc", size)
    except:
        try:
            return ImageFont.truetype("/System/Luigi/Library/Fonts/Helvetica.ttc" if not bold else
                                       "/System/Library/Fonts/Hiragino Sans GB.ttc", size)
        except:
            return ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc" if not bold else
                                       "/System/Library/Fonts/Hiragino Sans GB.ttc", size)

def base_scene(cold_top=True, warm_top=False):
    """创建分屏底图"""
    img = Image.new("RGB", (W, H), (10, 10, 15))
    draw = ImageDraw.Draw(img)
    # 左冷右暖渐变
    for x in range(W//2):
        t = x/(W//2)
        r = int(COLD[0]*(1-t)+CARD[0]*t)
        g = int(COLD[1]*(1-t)+CARD[1]*t)
        b = int(COLD[2]*(1-t)+CARD[2]*t)
        draw.line([(x,0),(x,H)], fill=(r,g,b))
    for x in range(W//2, W):
        t = (x-W//2)/(W//2)
        r = int(CARD[0]*(1-t)+WARM[0]*t)
        g = int(CARD[1]*(1-t)+WARM[1]*t)
        b = int(CARD[2]*(1-t)+WARM[2]*t)
        draw.line([(x,0),(x,H)], fill=(r,g,b))
    # 中间分割线
    draw.line([(W//2,0),(W//2,H)], fill=GOLD, width=3)
    return img, draw

def draw_person(draw, cx, cy, cold=True, posture="standing", alpha=180):
    """抽象人形，冷色或暖色"""
    col = (100,140,200) if cold else (200,170,90)
    col_alpha = (col[0],col[1],col[2])
    # 头
    draw.ellipse([cx-18,cy-60,cx+18,cy-24], fill=col_alpha)
    # 身体
    draw.rectangle([cx-22,cy-24,cx+22,cy+35], fill=col_alpha)
    if posture == "sitting":
        draw.rectangle([cx-30,cy+35,cx+30,cy+65], fill=col_alpha)
    elif posture == "lying":
        draw.line([cx-40,cy+50,cx+40,cy+50], fill=col_alpha, width=12)
    else:
        draw.rectangle([cx-30,cy+35,cx+30,cy+75], fill=col_alpha)
        draw.rectangle([cx-50,cy-10,cx-30,cy+20], fill=col_alpha)  # 左臂
        draw.rectangle([cx+30,cy-10,cx+50,cy+20], fill=col_alpha)  # 右臂

def draw_glow(draw, cx, cy, color=GOLD, radius=80):
    """光晕效果"""
    r, g, b = color
    for i in range(10, 0, -1):
        alpha = int(255*(10-i)/10*0.3)
        col = (min(255,r+i*3), min(255,g+i*3), min(255,b+i*3))
        draw.ellipse([cx-radius-i*3,cy-radius-i*3,
                      cx+radius+i*3,cy+radius+i*3],
                     fill=col)

def add_split_label(draw, left_text, right_text):
    """添加分屏标签"""
    fnt = get_font(22, bold=True)
    fnt2 = get_font(18)
    # 左标签
    draw.rectangle([20,20,280,65], fill=(0,0,0,200))
    draw.text((30,25), f"◀ {left_text}", font=fnt2, fill=GRAY)
    # 右标签
    draw.rectangle([W-280,20,W-20,65], fill=(0,0,0,200))
    draw.text((W-270,25), f"{right_text} ▶", font=fnt2, fill=GOLD)

def add_subtitle(draw, text, color=WHITE, y_offset=0):
    """底部字幕"""
    fnt = get_font(32, bold=True)
    bb = fnt.getbbox(text); bw = bb[2]-bb[0]; bh = bb[3]-bb[1]
    bx = (W-bw)//2
    draw.rectangle([bx-30,H-110+y_offset,bx+bw+30,H-40+y_offset], fill=(0,0,0,180))
    draw.text((bx, H-105+y_offset), text, font=fnt, fill=color)

def add_scene_number(draw, n):
    """场景编号"""
    fnt = get_font(16)
    draw.text((W-80, 20), f"场景 {n}/12", font=fnt, fill=GOLD)

# ============================================================
# 分镜1：开场分屏
# ============================================================
def make_scene1(n):
    img, draw = base_scene()
    # 裂开效果：中间黑色V形
    cx, cy = W//2, H//2
    pts = [(cx,0),(cx+8,0),(cx+60,cy-80),(cx+8,cy),(cx,cy+10),(cx-8,cy),(cx-60,cy-80),(cx-8,0)]
    draw.polygon(pts, fill=(5,5,10))
    add_split_label(draw, "没有元神", "有元神")
    add_subtitle(draw, "左：没有元神的一天  右：有元神的一天", GOLD, y_offset=-10)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_开场.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜2：闹钟醒来
# ============================================================
def make_scene2(n):
    img, draw = base_scene()
    # 左：闹钟（红闪）
    draw.rectangle([W//4-60,H//3-20,W//4+60,H//3+20], fill=(60,20,20))
    draw.text((W//4-30,H//3-12), "07:00", font=get_font(28,bold=True), fill=(255,80,80))
    # 冷色人躺着
    draw.line([W//4-60,H//2+60,W//4+60,H//2+60], fill=(80,120,180), width=16)
    draw.ellipse([W//4-20,H//2+20,W//4+20,H//2+60], fill=(80,120,180))
    draw.text((W//4-60,H//2+80), "继续睡...", font=get_font(18), fill=(100,100,100))

    # 右：金色晨光
    for y in range(0, H//2):
        t = y/(H//2)
        r = int(255*t); g = int(200*t); b = int(80*t)
        draw.line([(W//2+10,y),(W-10,y)], fill=(r,g,b))
    # 暖色人坐起
    draw.ellipse([3*W//4-18,H//2-60,3*W//4+18,H//2-24], fill=(200,170,90))
    draw.rectangle([3*W//4-22,H//2-24,3*W//4+22,H//2+35], fill=(200,170,90))
    # 元神光
    draw_glow(draw, 3*W//4+80, H//2-20, GOLD, 60)
    draw.text((3*W//4-80,H//2+50), "自然醒，元神已同步", font=get_font(16), fill=GOLD)

    add_split_label(draw, "闹钟狂响", "晨光自然醒")
    add_subtitle(draw, "闹钟狂响，继续沉睡", GRAY, y_offset=10)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_醒来.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜3：手机 vs 睡眠报告
# ============================================================
def make_scene3(n):
    img, draw = base_scene()
    # 左：手机慌乱
    draw.rectangle([W//4-50,H//2-80,W//4+50,H//2+80], fill=(30,30,40))
    draw.text((W//4-35,H//2-60), "99+", font=get_font(20,bold=True), fill=(255,50,50))
    draw.text((W//4-40,H//2-30), "消息", font=get_font(16), fill=(200,200,200))
    # 冷色人
    draw.ellipse([W//4-18,H//2+80,W//4+18,H//2+116], fill=(80,120,180))
    draw.rectangle([W//4-22,H//2+116,W//4+22,H//2+166], fill=(80,120,180))
    draw.text((W//4-60,H//2+180), "慌乱查看手机", font=get_font(14), fill=(120,120,140))

    # 右：元神睡眠报告
    draw.rectangle([3*W//4-120,H//2-130,3*W//4+120,H//2+60], fill=(20,35,60))
    draw.rectangle([3*W//4-120,H//2-130,3*W//4+120,H//2-130], fill=GOLD, width=3)
    draw.text((3*W//4-80,H//2-115), "元神 · 今日同步", font=get_font(16,bold=True), fill=GOLD)
    lines = ["深睡 5h42m ↑", "REM 1h20m", "REM 1h20m", "", "今日重点：", "· 决策准确率回升", "· 情绪波动-12%", "· 建议9:30后处理邮件"]
    for i, ln in enumerate(lines):
        c = GOLD if i <= 2 else WHITE if i >= 4 else GRAY
        draw.text((3*W//4-100,H//2-85+i*28), ln, font=get_font(16), fill=c)
    draw_glow(draw, 3*W//4+100, H//2-50, GOLD, 40)

    add_split_label(draw, "手机消息轰炸", "元神晨间报告")
    add_subtitle(draw, "被动接收 vs 主动理解", GRAY, y_offset=10)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_报告.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜4：办公室通知 vs 专注
# ============================================================
def make_scene4(n):
    img, draw = base_scene()
    # 左：通知轰炸
    for i in range(5):
        draw.rectangle([50+i*20, 80+i*40, 250+i*20, 130+i*40], fill=(40,20,20))
        draw.text((60+i*20, 88+i*40), f"通知 {i+1}", font=get_font(14), fill=(255,60,60))
    draw.ellipse([W//4-20,H//2+20,W//4+20,H//2+56], fill=(80,120,180))
    draw.rectangle([W//4-25,H//2+56,W//4+25,H//2+100], fill=(80,120,180))
    draw.text((W//4-80,H//2+115), "通知轰炸，手忙脚乱", font=get_font(14), fill=(120,80,80))

    # 右：专注工作+元神图标
    draw.rectangle([3*W//4-150,H//2-100,3*W//4+150,H//2+100], fill=(20,30,50))
    draw.text((3*W//4-80,H//2-80), "专注工作模式已开启", font=get_font(18,bold=True), fill=GOLD)
    draw.text((3*W//4-80,H//2-45), "✓ 消息已过滤", font=get_font(16), fill=(100,200,100))
    draw.text((3*W//4-80,H//2-20), "✓ 日程已同步", font=get_font(16), fill=(100,200,100))
    draw.text((3*W//4-80,H//2+5), "✓ 邮件已归类", font=get_font(16), fill=(100,200,100))
    draw_glow(draw, 3*W//4+110, H//2-50, GOLD, 50)
    draw.text((3*W//4-80,H//2+30), "元神在后台，安心工作", font=get_font(14), fill=GOLD)
    draw.ellipse([3*W//4-18,H//2+80,3*W//4+18,H//2+116], fill=(200,170,90))
    draw.rectangle([3*W//4-22,H//2+116,3*W//4+22,H//2+166], fill=(200,170,90))

    add_split_label(draw, "消息轰炸", "元神守护专注")
    add_subtitle(draw, "被干扰 vs 被守护", GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_专注.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜5：会议
# ============================================================
def make_scene5(n):
    img, draw = base_scene()
    # 左：翻找资料
    draw.rectangle([W//4-120,H//2-50,W//4+120,H//2+50], fill=(40,40,50))
    draw.text((W//4-80,H//2-30), "资料?", font=get_font(24,bold=True), fill=(200,60,60))
    draw.ellipse([W//4-18,H//2+55,W//4+18,H//2+91], fill=(80,120,180))
    draw.rectangle([W//4-22,H//2+91,W//4+22,H//2+141], fill=(80,120,180))
    draw.text((W//4-80,H//2+155), "翻找资料，同事不耐", font=get_font(14), fill=(140,100,100))

    # 右：元神投射要点
    draw.rectangle([3*W//4-150,H//2-130,3*W//4+150,H//2+80], fill=(15,30,55))
    draw.rectangle([3*W//4-150,H//2-130,3*W//4+150,H//2-130], fill=GOLD, width=3)
    draw.text((3*W//4-80,H//2-115), "元神 · 会议要点投射", font=get_font(16,bold=True), fill=GOLD)
    pts = ["1. Q3目标达成路径", "2. 竞品对比分析", "3. 下月资源需求", "4. 风险预案要点"]
    for i, pt in enumerate(pts):
        draw.text((3*W//4-120,H//2-80+i*38), f"● {pt}", font=get_font(17), fill=WHITE)
    draw_glow(draw, 3*W//4+110, H//2-30, GOLD, 50)
    draw.ellipse([3*W//4-18,H//2+85,3*W//4+18,H//2+121], fill=(200,170,90))
    draw.rectangle([3*W//4-22,H//2+121,3*W//4+22,H//2+171], fill=(200,170,90))
    draw.text((3*W//4-70,H//2+185), "从容发言，言之有物", font=get_font(14), fill=GOLD)

    add_split_label(draw, "翻找资料，手忙脚乱", "元神投射，从容发言")
    add_subtitle(draw, "准备不足 vs 心中有数", GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_会议.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜6：琴行
# ============================================================
def make_scene6(n):
    img, draw = base_scene()
    # 左：路过琴行无停
    draw.rectangle([W//4-100,H//3-80,W//4+100,H//3+80], fill=(50,40,30))  # 琴行
    draw.text((W//4-50,H//3-20), "🎸 琴行", font=get_font(20), fill=(100,80,60))
    # 冷色人背影（走过）
    draw.ellipse([W//4+20,H//2+10,W//4+58,H//2+46], fill=(60,100,160))
    draw.rectangle([W//4+16,H//2+46,W//4+62,H//2+100], fill=(60,100,160))
    draw.line([W//4+60,H//2+60,W//4+120,H//2+40], fill=(60,100,160), width=10)
    draw.text((W//4+60,H//2-20), "继续走...", font=get_font(18), fill=(120,120,140))

    # 右：收到元神提醒
    draw.rectangle([3*W//4-150,H//3-80,3*W//4+150,H//3+80], fill=(40,30,20))  # 琴行
    draw.text((3*W//4-50,H//3-20), "🎸 琴行", font=get_font(20), fill=GOLD)
    draw.rectangle([3*W//4-140,H//3-110,3*W//4+140,H//3-70], fill=(20,35,60))
    draw.text((3*W//4-100,H//3-102), "元神提醒", font=get_font(15,bold=True), fill=GOLD)
    draw.text((3*W//4-120,H//3-75), "吉他课 · 明晚19:00", font=get_font(16), fill=WHITE)
    draw.text((3*W//4-120,H//3-55), "你曾说要学一门乐器", font=get_font(14), fill=GRAY)
    # 暖色人推门
    draw.ellipse([3*W//4-18,H//2+10,3*W//4+18,H//2+46], fill=(200,170,90))
    draw.rectangle([3*W//4-22,H//2+46,3*W//4+22,H//2+100], fill=(200,170,90))
    draw.line([3*W//4-60,H//2+60,3*W//4-10,H//2+30], fill=(200,170,90), width=10)  # 推门
    draw_glow(draw, 3*W//4-5, H//2+20, GOLD, 40)
    draw.text((3*W//4-70,H//2+115), "推门而入，开始学吉他", font=get_font(14), fill=GOLD)

    add_split_label(draw, "路过琴行，脚步不停", "元神提醒，推门而入")
    add_subtitle(draw, "错过热爱 vs 找回热爱", GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_琴行.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜7：深夜刷手机 vs 阳台对话
# ============================================================
def make_scene7(n):
    img, draw = base_scene()
    # 左：深夜刷手机
    draw.rectangle([0,0,W//2,H], fill=(5,5,10))  # 纯黑左
    draw.rectangle([W//4-40,H//2-30,W//4+40,H//2+30], fill=(20,20,30))
    draw.text((W//4-30,H//2-15), "📱", font=get_font(24))
    draw.ellipse([W//4-18,H//2+35,W//4+18,H//2+71], fill=(50,80,120))
    draw.rectangle([W//4-22,H//2+71,W//4+22,H//2+121], fill=(50,80,120))
    draw.text((W//4-70,H//2+135), "深夜刷手机，越刷越空虚", font=get_font(14), fill=(100,100,120))

    # 右：阳台喝茶+元神投射
    draw.rectangle([W//2+10,0,W,H], fill=(8,6,3))  # 暖黑右
    # 月光渐变
    for y in range(0, H//2):
        t = y/(H//2)
        draw.line([(W//2+10,y),(W-10,y)], fill=(int(20+t*20),int(18+t*15),5))
    # 茶
    draw.ellipse([3*W//4-15,H//2-30,3*W//4+15,H//2], fill=(80,60,30))
    draw.text((3*W//4-50,H//2-50), "☕", font=get_font(20))
    # 元神投射
    draw.rectangle([3*W//4-140,H//3-80,3*W//4+140,H//3+60], fill=(15,30,55))
    draw.rectangle([3*W//4-140,H//3-80,3*W//4+140,H//3-80], fill=GOLD, width=3)
    draw.text((3*W//4-80,H//3-65), "元神 · 今日心路", font=get_font(16,bold=True), fill=GOLD)
    lines = ["今天你做了3个重要决定", "决策质量比昨天提升18%", "你找回了吉他课的初心", "", "你比自己以为的更坚定"]
    for i, ln in enumerate(lines):
        c = GOLD if i==4 else WHITE if i<4 else GRAY
        draw.text((3*W//4-100,H//3-40+i*28), ln, font=get_font(15), fill=c)
    draw_glow(draw, 3*W//4+110, H//3+10, GOLD, 60)
    # 暖色人
    draw.ellipse([3*W//4-18,H//2+15,3*W//4+18,H//2+51], fill=(200,170,90))
    draw.rectangle([3*W//4-22,H//2+51,3*W//4+22,H//2+100], fill=(200,170,90))
    draw.text((3*W//4-70,H//2+115), "阳台独处，与元神对话", font=get_font(14), fill=GOLD)

    add_split_label(draw, "深夜刷手机，越刷越孤独", "阳台喝茶，与元神对话")
    add_subtitle(draw, "消耗 vs 滋养", GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_阳台.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜8：辗转反侧 vs 元神道晚安
# ============================================================
def make_scene8(n):
    img, draw = base_scene()
    # 左：辗转
    draw.rectangle([0,0,W//2,H], fill=(3,3,8))
    draw.line([W//4-50,H//2,W//4+50,H//2+20], fill=(60,80,120), width=12)
    draw.ellipse([W//4-15,H//2-30,W//4+15,H//2+10], fill=(60,80,120))
    for i in range(3):
        draw.ellipse([W//4-100+i*60,H//2+30,W//4-80+i*60,H//2+50], fill=(30,30,40))
    draw.text((W//4-80,H//2+65), "辗转反侧，无法入眠", font=get_font(14), fill=(80,80,100))

    # 右：灯光渐暗+元神晚安
    draw.rectangle([W//2,0,W,H], fill=(10,8,5))
    for i in range(20, 0, -1):
        alpha = int(255*i/20*0.15)
        r2 = 150+i*5
        draw.ellipse([3*W//4-r2, H//2-r2, 3*W//4+r2, H//2+r2],
                     fill=(60+alpha,50+alpha,20))
    draw.rectangle([3*W//4-150,H//2-80,3*W//4+150,H//2+60], fill=(10,20,35))
    draw.text((3*W//4-70,H//2-60), "元神 · 晚安", font=get_font(22,bold=True), fill=GOLD)
    draw.text((3*W//4-90,H//2-25), "深睡质量预测：5.5h", font=get_font(16), fill=WHITE)
    draw.text((3*W//4-100,H//2+5), "明早我会提前15分钟唤醒你", font=get_font(14), fill=GRAY)
    draw.text((3*W//4-50,H//2+35), "🌙", font=get_font(24))
    # 暖色人（已入睡）
    draw.line([3*W//4-60,H//2+90,3*W//4+60,H//2+90], fill=(200,170,90), width=14)
    draw.ellipse([3*W//4-15,H//2+60,3*W//4+15,H//2+90], fill=(200,170,90))
    draw_glow(draw, 3*W//4, H//2+30, GOLD, 30)

    add_split_label(draw, "辗转反侧，难以入眠", "元神道晚安，灯光渐暗")
    add_subtitle(draw, "焦虑失眠 vs 安心入眠", GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_晚安.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜9：金色结语
# ============================================================
def make_scene9(n):
    img = Image.new("RGB", (W, H), (5, 5, 10))
    draw = ImageDraw.Draw(img)
    # 中心金字
    for r in range(80, 0, -1):
        alpha = int(255*(80-r)/80*0.15)
        draw.ellipse([W//2-r, H//2-60-r, W//2+r, H//2-60+r],
                     fill=(200+alpha,170+alpha,50+alpha))
    fnt = get_font(56, bold=True)
    text = "每一天，你都有两种活法。"
    bb = fnt.getbbox(text); bw = bb[2]-bb[0]
    draw.rectangle([W//2-bw//2-40,H//2-120,W//2+bw//2+40,H//2-30], fill=(0,0,0,200))
    draw.text((W//2-bw//2, H//2-110), text, font=fnt, fill=GOLD)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_宣言.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜10：蒙太奇
# ============================================================
def make_scene10(n):
    img = Image.new("RGB", (W, H), (8, 6, 3))
    draw = ImageDraw.Draw(img)
    # 四格蒙太奇
    scenes = [
        ((50,50,W//2-20,H//2-20), "🎸 练吉他", "找到热爱"),
        ((W//2+20,50,W-50,H//2-20), "💼 自信开会", "言之有物"),
        ((50,H//2+20,W//2-20,H-50), "🌙 阳台对话", "内心平静"),
        ((W//2+20,H//2+20,W-50,H-50), "🎹 陪女儿", "回归热爱"),
    ]
    colors2 = [(60,50,20),(50,40,20),(40,35,15),(55,45,18)]
    for i, scene in enumerate(scenes):
        l,t,r,b = scene[0]
        emoji = scene[1]
        label = scene[2]
        draw.rectangle([l,t,r,b], fill=colors2[i])
        draw.rectangle([l,t,r,b], outline=GOLD, width=2)
        draw.text((l+20,t+20), emoji, font=get_font(36))
        draw.text((l+20,t+80), label, font=get_font(26,bold=True), fill=GOLD)
        sub = scene[3] if len(scene)>3 else ""
        draw.text((l+20,t+115), sub, font=get_font(18), fill=GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_蒙太奇.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜11：阳台背影
# ============================================================
def make_scene11(n):
    img = Image.new("RGB", (W, H), (8, 6, 3))
    draw = ImageDraw.Draw(img)
    # 日出渐变
    for y in range(0, H//2):
        t = y/(H//2)*0.7
        r = int(255*t); g = int(180*t); b = int(60*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    for y in range(H//2, H):
        draw.line([(0,y),(W,y)], fill=(8,6,3))
    # 阳台栏杆
    draw.line([0,H//2+80,W,H//2+80], fill=(40,35,20), width=4)
    for x in range(0,W,60):
        draw.line([(x,H//2+60),(x,H//2+100)], fill=(50,45,25), width=2)
    # 人物背影
    cx, cy = W//2, H//2+20
    draw.ellipse([cx-30,cy-100,cx+30,cy-40], fill=(200,170,90))  # 头
    draw.rectangle([cx-35,cy-40,cx+35,cy+60], fill=(200,170,90))  # 身体
    # 元神光
    draw_glow(draw, cx+80, cy-20, GOLD, 70)
    draw.text((cx+100,cy-40), "元神", font=get_font(18,bold=True), fill=GOLD)
    fnt = get_font(20)
    draw.text((cx+100,cy-15), "一直在", font=fnt, fill=GRAY)
    # 眼中光芒
    draw.ellipse([cx-8,cy-60,cx+8,cy-44], fill=(255,255,200))

    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_背影.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# 分镜12：封底黑屏
# ============================================================
def make_scene12(n):
    img = Image.new("RGB", (W, H), (5, 5, 10))
    draw = ImageDraw.Draw(img)
    # 金字
    for r in range(120, 0, -1):
        draw.ellipse([W//2-r, H//2-60-r, W//2+r, H//2-60+r],
                     fill=(180+r,150+r,30+r))
    fnt1 = get_font(52, bold=True)
    fnt2 = get_font(36)
    t1 = "把生活交给AI，把人生还给热爱。"
    bb1 = fnt1.getbbox(t1); bw1 = bb1[2]-bb1[0]
    draw.rectangle([W//2-bw1//2-30,H//2-100,W//2+bw1//2+30,H//2-20], fill=(0,0,0))
    draw.text((W//2-bw1//2, H//2-90), t1, font=fnt1, fill=GOLD)
    # Logo
    t2 = "元神AI · META SOUL"
    bb2 = fnt2.getbbox(t2); bw2 = bb2[2]-bb2[0]
    draw.text((W//2-bw2//2, H//2+20), t2, font=fnt2, fill=GRAY)
    add_scene_number(draw, n)
    path = OUT/f"scene{n:02d}_封底.png"
    img.save(path); print(f"  [{n}] {path.name}")
    return path

# ============================================================
# HTML动画生成
# ============================================================
def make_html_animation():
    scenes_files = sorted([str(f) for f in OUT.glob("scene*.png")])
    html = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>第四幕·普通人的一天</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;font-family:Arial,sans-serif}
.screen{position:relative;width:960px;height:409px;border:1px solid #333;overflow:hidden;background:#0a0a0f}
.split{position:absolute;top:0;bottom:0;left:0;width:50%;background:linear-gradient(180deg,#1a2638 0%,#0d1520 100%)}
.split-r{position:absolute;top:0;bottom:0;right:0;width:50%;background:linear-gradient(180deg,#1a1505 0%,#08060a 100%)}
.divider{position:absolute;top:0;bottom:0;left:50%;width:3px;background:linear-gradient(180deg,#d4af37,#8b6914);z-index:10}
.center-v{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:60px;height:60px;background:#0a0a0f;border-radius:50%;z-index:11;display:flex;align-items:center;justify-content:center}
.center-v span{color:#d4af37;font-size:24px}
.glow{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(212,175,55,0.6) 0%,transparent 70%);width:80px;height:80px;z-index:5}
.glow-l{left:calc(50% - 120px);top:50%;transform:translateY(-50%)}
.glow-r{right:calc(50% - 120px);top:50%;transform:translateY(-50%)}
.info{position:absolute;bottom:20px;left:0;right:0;text-align:center;z-index:20}
.info span{background:rgba(0,0,0,0.7);color:#d4af37;padding:6px 20px;font-size:13px;border-radius:4px}
.progress{width:960px;height:4px;background:#222;margin-top:10px;border-radius:2px;overflow:hidden}
.progress-bar{height:100%;background:linear-gradient(90deg,#2196F3,#d4af37);width:0%;transition:width 0.1s}
.controls{display:flex;gap:10px;margin-top:15px;align-items:center}
.btn{background:#1a2535;border:1px solid #d4af37;color:#d4af37;padding:8px 24px;cursor:pointer;font-size:13px;border-radius:4px}
.btn:hover{background:#d4af37;color:#000}
.time{color:#94a3b8;font-size:13px;min-width:80px;text-align:center}
</style>
</head>
<body>
<div class="screen" id="screen">
  <div class="split" id="splitL"></div>
  <div class="split-r" id="splitR"></div>
  <div class="divider"></div>
  <div class="glow glow-l" id="glowL"></div>
  <div class="glow glow-r" id="glowR"></div>
  <div class="center-v"><span>⇆</span></div>
  <div class="info" id="info"><span id="infoText">每一天，你都有两种活法</span></div>
</div>
<div class="progress"><div class="progress-bar" id="progressBar"></div></div>
<div class="controls">
  <button class="btn" onclick="togglePlay()">▶ 播放</button>
  <button class="btn" onclick="resetAnim()">⟲ 重播</button>
  <span class="time" id="timeDisplay">0s / 90s</span>
</div>
<script>
const screen = document.getElementById('screen');
const infoText = document.getElementById('infoText');
const progressBar = document.getElementById('progressBar');
const timeDisplay = document.getElementById('timeDisplay');
let playing = false, startTime = 0, pausedAt = 0;
const TOTAL = 90;

const phases = [
  {t:3,s:"左：没有元神的一天  右：有元神的一天",bgL:"#0d1520",bgR:"#08060a",glow:true},
  {t:8,s:"闹钟狂响，继续沉睡 vs 晨光自然醒",bgL:"#1a1a25",bgR:"#1a1205",glow:true},
  {t:13,s:"被动接收 vs 主动理解",bgL:"#0d1520",bgR:"#0a1505",glow:true},
  {t:20,s:"被干扰 vs 被守护",bgL:"#1a0d15",bgR:"#0a1505",glow:true},
  {t:27,s:"准备不足 vs 心中有数",bgL:"#1a1a25",bgR:"#100a05",glow:true},
  {t:35,s:"错过热爱 vs 找回热爱",bgL:"#0d1015",bgR:"#151005",glow:true},
  {t:43,s:"消耗 vs 滋养",bgL:"#050510",bgR:"#080603",glow:true},
  {t:51,s:"焦虑失眠 vs 安心入眠",bgL:"#030310",bgR:"#080604",glow:true},
  {t:60,s:"每一天，你都有两种活法",bgL:"#0a0a15",bgR:"#0a0805",glow:true},
  {t:75,s:"热爱生活的日常",bgL:"#080603",bgR:"#080603",glow:false},
  {t:85,s:"把生活交给AI，把人生还给热爱",bgL:"#030305",bgR:"#030305",glow:false},
  {t:90,s:"元神AI · META SOUL",bgL:"#030305",bgR:"#030305",glow:false},
];

let animId;
function animate(ts){
  if(!playing) return;
  let elapsed = pausedAt + (ts - startTime)/1000;
  if(elapsed > TOTAL){ playing=false; document.querySelector('.btn').textContent="▶ 播放"; return; }
  progressBar.style.width = (elapsed/TOTAL*100)+"%";
  const s = Math.floor(elapsed);
  timeDisplay.textContent = s+"s / "+TOTAL+"s";
  let phase = phases[0];
  let cumT = 0;
  for(let p of phases){ cumT += p.t; if(elapsed < cumT){ phase = p; break; } }
  document.getElementById('splitL').style.background = `linear-gradient(180deg,${phase.bgL} 0%,#0a0a10 100%)`;
  document.getElementById('splitR').style.background = `linear-gradient(180deg,${phase.bgR} 0%,#08060a 100%)`;
  const gL = document.getElementById('glowL');
  const gR = document.getElementById('glowR');
  if(phase.glow){ gL.style.opacity=0.8; gR.style.opacity=0.8; } else { gL.style.opacity=0; gR.style.opacity=0; }
  infoText.textContent = phase.s;
  animId = requestAnimationFrame(animate);
}
function togglePlay(){
  if(playing){
    playing=false; pausedAt += (performance.now()-startTime)/1000;
    document.querySelector('.btn').textContent="▶ 播放";
  } else {
    playing=true; startTime=performance.now();
    document.querySelector('.btn').textContent="⏸ 暂停";
    animId=requestAnimationFrame(animate);
  }
}
function resetAnim(){ playing=false; pausedAt=0; progressBar.style.width="0%"; timeDisplay.textContent="0s / 90s";
  document.getElementById('infoText').textContent="每一天，你都有两种活法";
  document.getElementById('splitL').style.background="";
  document.getElementById('splitR').style.background="";
  document.querySelector('.btn').textContent="▶ 播放";
}
</script>
</body>
</html>"""
    path = OUT/"第四幕_动画演示.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML动画: {path.name}")
    return path

# ============================================================
# CapCut提示词文档
# ============================================================
def make_capcut_doc():
    doc = """# 第四幕《普通人的一天》CapCut制作指南

## 基本信息
- 时长：90秒
- 画幅：2.35:1 (1920×817)
- 分镜：12个场景
- 色调：左侧冷蓝灰 / 右侧暖金色
- 配乐：CapCut搜索"Cinematic Hope Piano"

---

## 分镜详解

### 场景1｜开场分屏（0-3秒）
- 内容：黑屏，中间裂开，左冷右暖，同一卧室
- 字幕：「左：没有元神的一天  右：有元神的一天」
- 运镜：缓慢zoom in

### 场景2｜闹钟醒来（4-8秒）
- 左：闹钟狂响，按掉继续睡
- 右：窗帘自动拉开，晨光洒入，自然醒
- 元神语音：「早上好，你昨晚深睡5小时42分钟，比昨天多15分钟」
- CapCut提示词（通义万相）：
  `split screen, left side cold blue tone man waking up late with loud alarm clock ringing, right side warm golden tone man waking up naturally with sunlight streaming through curtains and soft music, cinematic 2.35:1`

### 场景3｜手机报告（9-13秒）
- 左：手机通知99+，慌乱起身
- 右：床头屏幕显示元神《今日晨间报告》（深睡/REM/情绪数据）
- 元神语音：「今天你的决策准确率预计比昨天提升12%」
- CapCut提示词：
  `split screen, left side cold tone messy morning man checking phone with dozens of notifications, right side warm tone holographic AI morning report display showing sleep data and daily briefing, cinematic`

### 场景4｜办公室专注（14-20秒）
- 左：电脑前通知轰炸，手忙脚乱
- 右：专注工作，元神图标安静发光，消息已过滤
- CapCut提示词：
  `split screen, left side cold tone office worker overwhelmed by notification popups cluttered screen, right side warm tone focused professional with AI assistant icon glowing softly filtering notifications, clean desk, cinematic`

### 场景5｜会议发言（21-27秒）
- 左：会议中翻找资料，同事不耐烦
- 右：元神要点从容投射，言之有物
- CapCut提示词：
  `split screen, left side cold tone meeting room man frantically searching through papers colleagues looking impatient, right side warm tone meeting room confident speaking with holographic AI key points floating above table, cinematic`

### 场景6｜琴行（28-35秒）
- 左：下班路过琴行，没停步
- 右：收到元神提醒「吉他课·明晚19:00」，推门进琴行
- 元神语音：「你曾说想学一门乐器，今晚刚好有名额」
- CapCut提示词：
  `split screen, left side cold tone man walking past guitar shop looking tired and distracted, right side warm tone man receiving holographic AI notification on phone about guitar lesson and entering music shop, golden hour light, cinematic`

### 场景7｜深夜阳台（36-43秒）
- 左：深夜独自刷手机，越刷越空虚
- 右：阳台喝茶，元神投射《今日心路》
- 元神语音：「今天你做了3个重要决定，决策质量比昨天提升了18%」
- CapCut提示词：
  `split screen, left side dark cold tone man alone on couch scrolling phone late night blue light, right side warm tone peaceful balcony with tea and holographic AI daily reflection report glowing softly, moonlight, cinematic`

### 场景8｜晚安（44-51秒）
- 左：辗转反侧睡不着
- 右：灯光渐暗，元神道晚安
- 元神语音：「深睡质量预测5.5小时，明早我提前15分钟唤醒你。晚安。」
- CapCut提示词：
  `split screen, left side cold tone man restless in bed unable to sleep turning over, right side warm tone peaceful bedroom with AI voice goodnight soft dimming warm light gradually fading, sleep mode, cinematic`

### 场景9｜宣言（52-60秒）
- 画面：左右缩小，中心金字浮现
- 字幕：「每一天，你都有两种活法」
- 右侧渐入全屏，主角晨光中睁眼微笑
- 无配乐，留白

### 场景10｜蒙太奇（61-75秒）
- 四个画面快速闪过（弹吉他/自信开会/阳台对话/陪女儿弹钢琴）
- 配乐渐强
- CapCut提示词：
  `montage warm golden tone, man learning guitar in music shop, confident speaking in business meeting, peaceful evening balcony AI conversation, father playing piano with young daughter in living room, joyful family moment, cinematic`

### 场景11｜阳台背影（76-85秒）
- 主角阳台背影，身边有淡淡金色光影
- 转身，眼中有光
- CapCut提示词：
  `warm golden tone sunrise, man standing on balcony looking at city view, soft glowing AI presence beside him as light orb, man turns to camera with light reflected in eyes, serene confident expression, cinematic`

### 场景12｜封底（86-90秒）
- 黑屏
- 金字：「把生活交给AI，把人生还给热爱。」
- 元神AI Logo淡入
- 配乐渐弱淡出

---

## AI配音脚本（截取使用）

**场景2 元神晨音：**
「早上好。你昨晚深睡5小时42分钟，比前天多了15分钟。今天你的状态，适合处理那件拖了一周的重要决策。」

**场景3 晨间报告：**
「今日重点：决策准确率预计比昨天提升12%；情绪波动-8%；建议9:30之后统一处理邮件。」

**场景6 元神提醒：**
「你曾说想学一门乐器，今晚吉他课有名额。要帮你预约吗？」

**场景7 今日心路：**
「今天你做了3个重要决定。决策质量比昨天提升了18%。你找回了当初学吉他的初心。你比自己以为的更坚定。」

**场景8 晚安：**
「深睡质量预测5小时30分钟。明早我会提前15分钟唤醒你。今天，你活得很真实。晚安。」

---

## CapCut操作步骤
1. 新建项目，比例选「电影2.35:1」
2. 导入本文件夹中的12张PNG故事板作为关键帧参考
3. 搜索配乐"Cinematic Hope Piano"，导入
4. 按上述时间轴顺序剪辑
5. 在场景2/3/6/7/8插入AI配音（可用TTS工具生成或手动录制）
6. 导出MP4，1080P
"""
    path = OUT/"第四幕_CapCut制作指南.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"  CapCut指南: {path.name}")
    return path

# ============================================================
# 主程序
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("第四幕《普通人的一天》生成器")
    print("=" * 50)
    print(f"\n输出目录: {OUT.resolve()}\n")

    print("[Step 1] 生成分镜故事板...")
    make_scene1(1)
    make_scene2(2)
    make_scene3(3)
    make_scene4(4)
    make_scene5(5)
    make_scene6(6)
    make_scene7(7)
    make_scene8(8)
    make_scene9(9)
    make_scene10(10)
    make_scene11(11)
    make_scene12(12)

    print("\n[Step 2] 生成HTML动画演示...")
    make_html_animation()

    print("\n[Step 3] 生成CapCut制作指南...")
    make_capcut_doc()

    print("\n" + "=" * 50)
    print("✅ 全部生成完成！")
    print("=" * 50)
    print(f"\n📁 输出目录: {OUT.resolve()}")
    print("\n生成内容:")
    total_size = 0
    for f in sorted(OUT.iterdir()):
        sz = f.stat().st_size
        total_size += sz
        print(f"  📷 {f.name} ({sz//1024}KB)")
    print(f"\n总大小: {total_size//1024}KB")
    print("\n下一步:")
    print("  1. 用浏览器打开 HTML动画演示.html 预览效果")
    print("  2. 按 CapCut制作指南.md 在CapCut中剪辑")
    print("  3. 使用通义万相等工具生成视频片段")
    print("  4. 导出MP4发至飞书群")
