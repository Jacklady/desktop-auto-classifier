# -*- coding: utf-8 -*-
"""核心分类引擎：规则分类、扫描、整理、撤销。纯标准库实现。"""
import json
import os
import shutil
import datetime
from pathlib import Path

CATEGORY_FOLDERS = [
    "学习-课程作业", "课程设计-毕业设计", "学生工作-党务团务",
    "项目-API对接开发", "项目-接码验证码", "项目-电商闲鱼",
    "项目-VR-Unity", "项目-SweetHeart情侣应用",
    "软件-工具", "个人-简历软著", "媒体-素材", "杂项-其他",
]
MISC = "杂项-其他"

# 不移动的内容：快捷方式、隐藏/系统文件、分类文件夹自身、本程序
SKIP_NAMES = {"desktop.ini", "$RECYCLE.BIN", "System Volume Information",
              "桌面自动分类器.exe", "DesktopAutoClassifier.exe"}
SKIP_PREFIX = ("~$", ".")
SKIP_SUFFIX = (".lnk", ".url")

# ===== 规则 1：精确名称表（可自行在 json 里扩充）=====
EXACT = {
    "个人软著": "个人-简历软著",
}

# ===== 规则 2：关键词规则（按顺序匹配，先命中先归类）=====
RULES = [
    ("课程设计-毕业设计", ["课程设计", "毕业设计", "毕设", "机械设计", "开题"]),
    ("学习-课程作业", ["习题", "作业", "实验", "微机原理", "汇编", "装配工艺", "特种加工",
                    "数控", "工艺学", "背题", "题目", "雨课堂", "实习", "文献", "培训", "课件", "教案"]),
    ("学生工作-党务团务", ["党员", "党务", "团校", "团支部", "志愿服务", "志愿", "谈心", "三下乡",
                        "评议", "整改", "推优", "挑战杯", "签到表", "宣讲会", "先进个人", "集体"]),
    ("项目-接码验证码", ["接码", "验证码", "取号", "卡商", "号码代理", "短信平台"]),
    ("项目-电商闲鱼", ["闲鱼", "淘宝", "支付宝", "美团", "商城", "电商", "发货", "刷单"]),
    ("项目-VR-Unity", ["unitypackage", "unity", "vr开发", "pico", "xr", "骨骼vr", "座舱"]),
    ("项目-SweetHeart情侣应用", ["sweetheart", "情侣", "lover"]),
    ("项目-API对接开发", ["api", "爬虫", "对接", "反代", "服务器端", "后端", "backend", "jwt",
                       "codex", "接口", "大模型", "gpt", "deepseek", "逆向", "抓包", "签名"]),
    ("个人-简历软著", ["简历", "软著", "个人介绍", "就业", "求职", "面试"]),
    ("软件-工具", ["装系统", "清理", "注册表", "瘦身", "驱动", "刷机", "破解", "激活",
                 "工具", "指南", "扫描", "修复", "优化"]),
    ("媒体-素材", ["歌单", "壁纸", "素材", "字体", "音乐", "视频脚本"]),
]
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".mp3", ".mp4", ".avi",
             ".mkv", ".mov", ".wav", ".flac", ".ttf", ".ttc", ".otf", ".psd"}


def classify(name: str) -> str:
    low = name.lower()
    if name in EXACT:
        return EXACT[name]
    for cat, kws in RULES:
        for kw in kws:
            if kw in low:
                return cat
    if os.path.splitext(low)[1] in MEDIA_EXT:
        return "媒体-素材"
    return MISC


def _should_skip(p: Path) -> bool:
    n = p.name
    if n in SKIP_NAMES or n in CATEGORY_FOLDERS:
        return True
    if n.startswith(SKIP_PREFIX):
        return True
    if n.lower().endswith(SKIP_SUFFIX):
        return True
    return False


def scan(base: Path):
    """返回 [(路径, 分类, 名称, 依据)]，依据 = 规则/AI"""
    return [(p, classify(p.name), p.name, "规则") for p in
            sorted(base.iterdir(), key=lambda x: x.name.lower()) if not _should_skip(p)]


def app_dir(base: Path) -> Path:
    return base / ".autoclassifier"


def apply(base: Path, plan, progress=None, app_dir: Path = None):
    """plan: [(路径, 分类, 名称)]；每次整理写还原清单到 app_dir/latest.json"""
    ad = Path(app_dir) if app_dir else base / ".autoclassifier"
    ad.mkdir(parents=True, exist_ok=True)
    for c in CATEGORY_FOLDERS:
        (base / c).mkdir(exist_ok=True)
    moves, failures = [], []
    for idx, (src, cat, name) in enumerate(plan):
        dst_dir = base / cat
        dst = dst_dir / name
        if dst.exists():
            i = 2
            while (dst_dir / f"{src.stem} ({i}){src.suffix}").exists():
                i += 1
            dst = dst_dir / f"{src.stem} ({i}){src.suffix}"
        try:
            shutil.move(str(src), str(dst))
            moves.append({"name": name, "from": str(src), "to": str(dst)})
        except Exception as e:
            failures.append({"name": name, "error": str(e)})
        if progress:
            progress(idx + 1, len(plan))
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {"time": stamp, "base": str(base), "moves": moves}
    (ad / f"manifest_{stamp}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (ad / "latest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return moves, failures


def undo(base: Path, app_dir: Path = None):
    ad = Path(app_dir) if app_dir else base / ".autoclassifier"
    latest = ad / "latest.json"
    if not latest.exists():
        return [], "没有可撤销的整理记录"
    data = json.loads(latest.read_text(encoding="utf-8"))
    restored, failures = [], []
    for m in reversed(data["moves"]):
        src, dst = Path(m["to"]), Path(m["from"])
        try:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                restored.append(m["name"])
            else:
                failures.append(f"{m['name']}: 当前位置不存在")
        except Exception as e:
            failures.append(f"{m['name']}: {e}")
    latest.unlink(missing_ok=True)
    return restored, failures
