# -*- coding: utf-8 -*-
"""图形界面 v3：一键分类 + AI 智能识别 + 设置面板。

设计：shadcn/ui 风格令牌（浅色）、尼尔森启发式（系统状态可见、防误操作、可撤销）。
布局要点：底部操作栏先 pack（side=bottom），主列表最后 pack 占据剩余空间，
确保任何窗口尺寸下按钮都不会被挤出视野。
"""
import json
import os
import sys
import threading
import queue
import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import core
from . import llm

# ---------- 设计令牌（shadcn/ui 浅色主题） ----------
C = {
    "bg": "#F8FAFC", "card": "#FFFFFF", "border": "#E2E8F0",
    "text": "#0F172A", "muted": "#64748B",
    "primary": "#2563EB", "primary_hover": "#1D4ED8",
    "success": "#16A34A", "danger": "#DC2626", "warning": "#D97706",
}
CAT_COLOR = {
    "学习-课程作业": "#2563EB", "课程设计-毕业设计": "#7C3AED", "学生工作-党务团务": "#C2410C",
    "项目-API对接开发": "#0891B2", "项目-接码验证码": "#B45309", "项目-电商闲鱼": "#BE185D",
    "项目-VR-Unity": "#4F46E5", "项目-SweetHeart情侣应用": "#DB2777",
    "软件-工具": "#15803D", "个人-简历软著": "#0F766E", "媒体-素材": "#A16207",
    "杂项-其他": "#64748B",
}

CONFIG_FILE = "分类器配置.json"
LOG_FILE = "运行日志.txt"


def log_app(base: Path, msg: str):
    try:
        d = base / ".autoclassifier"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


def load_config(base: Path) -> dict:
    cfg = {"base_url": "", "api_key": "", "model": "", "ai_enabled": False}
    p = base / CONFIG_FILE
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def save_config(base: Path, cfg: dict):
    (base / CONFIG_FILE).write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def run_gui():
    # 默认目录：exe/脚本所在目录若像桌面（含分类文件夹）就用它，否则用当前目录
    home = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    if any((home / c).exists() for c in core.CATEGORY_FOLDERS) or (home / "desktop.ini").exists():
        default_base = home
    else:
        default_base = Path.cwd()

    root = tk.Tk()
    root.title("桌面自动分类器")
    root.geometry("820x640")
    root.minsize(700, 540)
    root.configure(bg=C["bg"])

    # 迁移旧版撤销记录（历史版本存放在 .workbuddy/自动分类备份）
    try:
        old_dir = default_base / ".workbuddy" / "自动分类备份"
        new_dir = default_base / ".autoclassifier"
        if old_dir.exists() and not (new_dir / "latest.json").exists():
            new_dir.mkdir(parents=True, exist_ok=True)
            import shutil as _shutil
            for f in list(old_dir.glob("latest.json")) + list(old_dir.glob("manifest_*.json")):
                _shutil.copy2(f, new_dir / f.name)
    except Exception:
        pass
    from tkinter import font as tkfont
    tkfont.nametofont("TkDefaultFont").configure(family="Microsoft YaHei UI", size=10)
    root.option_add("*Font", ("Microsoft YaHei UI", 10))

    state = {"base": default_base, "cfg": load_config(default_base), "plan": [], "busy": False}
    q = queue.Queue()

    # ---------- 按钮工厂 ----------
    def flat_btn(parent, text, kind, command=None, state="normal", side="left"):
        if kind == "primary":
            bg, fg, ab, padx, pady, weight = C["primary"], "#FFF", C["primary_hover"], 30, 10, "bold"
        elif kind == "secondary":
            bg, fg, ab, padx, pady, weight = C["card"], C["text"], "#F1F5F9", 14, 8, "normal"
        else:
            bg, fg, ab, padx, pady, weight = C["bg"], C["primary"], "#E0E9FB", 12, 8, "normal"
        b = tk.Button(parent, text=text, command=(command or (lambda: None)),
                      bg=bg, fg=fg, activebackground=ab, activeforeground=fg,
                      relief="flat", bd=0, padx=padx, pady=pady, cursor="hand2",
                      state=state, font=("Microsoft YaHei UI", 11 if kind == "primary" else 10, weight),
                      disabledforeground="#A8B3C5")
        b.pack(side=side, padx=(0 if side == "left" else 6, 6 if side == "left" else 0))
        if kind == "secondary":
            b.configure(highlightbackground=C["border"], highlightthickness=1)
        if state != "disabled":
            b.bind("<Enter>", lambda e, w=b, c=ab: w.configure(bg=c))
            b.bind("<Leave>", lambda e, w=b, c=bg: w.configure(bg=c))
        return b

    def make_chip(parent, label, value, color):
        chip = tk.Frame(parent, bg=C["card"], padx=14, pady=8,
                        highlightbackground=C["border"], highlightthickness=1)
        big = tk.Label(chip, text=value, font=("Microsoft YaHei UI", 14, "bold"),
                       bg=C["card"], fg=color)
        big.pack(anchor="w")
        tk.Label(chip, text=label, font=("Microsoft YaHei UI", 9),
                 bg=C["card"], fg=C["muted"]).pack(anchor="w")
        chip._value_label = big
        return chip

    # ---------- 底部操作栏（最先 pack，保证永不被挤出视野） ----------
    bottom = tk.Frame(root, bg=C["bg"])
    bottom.pack(side="bottom", fill="x", padx=20, pady=(6, 14))
    status_var = tk.StringVar(value="正在扫描…")
    status = tk.Label(bottom, textvariable=status_var, bg=C["bg"], fg=C["muted"],
                      font=("Microsoft YaHei UI", 9), anchor="w")
    status.pack(side="top", anchor="w", pady=(0, 8))
    style = ttk.Style()
    style.theme_use("default")
    style.configure("blue.Horizontal.TProgressbar", troughcolor=C["border"],
                    background=C["primary"], thickness=6)
    progress = ttk.Progressbar(bottom, mode="determinate",
                               style="blue.Horizontal.TProgressbar")
    btnrow = tk.Frame(bottom, bg=C["bg"])
    btnrow.pack(fill="x")
    btn_undo = flat_btn(btnrow, "↩ 撤销上次", "secondary", state="disabled", side="right")
    btn_open = flat_btn(btnrow, "打开文件夹", "ghost", side="right")
    btn_scan = flat_btn(btnrow, "重新扫描", "ghost", side="right")
    btn_ai = flat_btn(btnrow, "⚙ AI 设置", "secondary", side="right")
    btn_apply = flat_btn(btnrow, "🚀 一键分类", "primary", state="disabled", side="left")

    # ---------- 顶部 ----------
    header = tk.Frame(root, bg=C["bg"])
    header.pack(fill="x", padx=20, pady=(16, 6))
    tk.Label(header, text="桌面自动分类器", font=("Microsoft YaHei UI", 16, "bold"),
             bg=C["bg"], fg=C["text"]).pack(anchor="w")
    tk.Label(header, text="规则识别 + AI 智能分类。快捷方式、系统文件、隐藏目录永远不会被移动。",
             font=("Microsoft YaHei UI", 9), bg=C["bg"], fg=C["muted"]).pack(anchor="w", pady=(2, 0))

    dirrow = tk.Frame(root, bg=C["card"], padx=12, pady=9,
                      highlightbackground=C["border"], highlightthickness=1)
    dirrow.pack(fill="x", padx=20)
    tk.Label(dirrow, text="目标文件夹", bg=C["card"], fg=C["muted"],
             font=("Microsoft YaHei UI", 9)).pack(side="left")
    var_path = tk.StringVar(value=str(default_base))
    tk.Entry(dirrow, textvariable=var_path, relief="flat", bg=C["bg"], fg=C["text"],
             font=("Microsoft YaHei UI", 9)).pack(side="left", fill="x", expand=True,
                                                  padx=8, ipady=3)
    tk.Button(dirrow, text="浏览…", command=lambda: pick_dir(),
              bg=C["bg"], fg=C["primary"], activebackground="#E0E9FB",
              activeforeground=C["primary"], relief="flat", bd=0, padx=12, pady=6,
              cursor="hand2", font=("Microsoft YaHei UI", 9)).pack(side="right")

    # ---------- 状态卡片 ----------
    stats = tk.Frame(root, bg=C["bg"])
    stats.pack(fill="x", padx=20, pady=12)
    chip_pending = make_chip(stats, "待整理项目", "—", C["primary"])
    chip_ai = make_chip(stats, "AI 智能分类", "未启用", C["muted"])
    chip_protected = make_chip(stats, "受保护", "快捷方式·系统文件", C["success"])
    for chip in (chip_pending, chip_ai, chip_protected):
        chip.pack(side="left", padx=(0, 10), fill="x", expand=True)

    # ---------- 主列表（最后 pack，占据剩余空间） ----------
    list_wrap = tk.Frame(root, bg=C["card"],
                         highlightbackground=C["border"], highlightthickness=1)
    list_wrap.pack(fill="both", expand=True, padx=20)

    style.configure("Treeview", background=C["card"], fieldbackground=C["card"],
                    foreground=C["text"], rowheight=30, borderwidth=0,
                    font=("Microsoft YaHei UI", 10))
    style.configure("Treeview.Heading", background=C["bg"], foreground=C["muted"],
                    relief="flat", font=("Microsoft YaHei UI", 9, "bold"), padding=6)
    style.map("Treeview", background=[("selected", "#DBEAFE")],
              foreground=[("selected", C["text"])])

    tree = ttk.Treeview(list_wrap, columns=("name", "cat", "src"),
                        show="headings", selectmode="none")
    tree.heading("name", text="项目")
    tree.heading("cat", text="归入分类")
    tree.heading("src", text="识别方式")
    tree.column("name", width=420, anchor="w")
    tree.column("cat", width=230, anchor="w")
    tree.column("src", width=80, anchor="center", stretch=False)
    vsb = ttk.Scrollbar(list_wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for cat, color in CAT_COLOR.items():
        tree.tag_configure(f"c_{cat}", foreground=color)
    tree.tag_configure("stripe", background="#F8FAFC")

    # ---------- 业务逻辑 ----------
    def ai_ready():
        cfg = state["cfg"]
        return bool(cfg.get("ai_enabled") and cfg.get("base_url") and cfg.get("api_key") and cfg.get("model"))

    def refresh_ai_chip():
        if ai_ready():
            chip_ai._value_label.configure(text=f"已启用·{state['cfg']['model']}", fg=C["success"])
        else:
            chip_ai._value_label.configure(text="未启用", fg=C["muted"])

    def get_base():
        b = Path(var_path.get().strip())
        if not b.exists():
            messagebox.showerror("错误", "目标文件夹不存在，请检查路径")
            return None
        state["base"] = b
        return b

    def set_busy(busy):
        state["busy"] = busy
        for w in (btn_apply, btn_scan, btn_undo, btn_ai):
            w.configure(state="disabled" if busy else "normal")
        if not busy:
            if not state["plan"]:
                btn_apply.configure(state="disabled")
            if not (state["base"] / ".autoclassifier" / "latest.json").exists():
                btn_undo.configure(state="disabled")

    def fill_tree():
        tree.delete(*tree.get_children())
        stripe = False
        for p, cat, name, src in state["plan"]:
            tags = [f"c_{cat}"]
            if stripe:
                tags.append("stripe")
            tree.insert("", "end", values=(name, cat, src), tags=tags)
            stripe = not stripe

    def read_last_time():
        latest = state["base"] / ".autoclassifier" / "latest.json"
        if latest.exists():
            try:
                t = json.loads(latest.read_text(encoding="utf-8")).get("time", "")
                if t:
                    return f"{t[0:4]}-{t[4:6]}-{t[6:8]} {t[9:11]}:{t[11:13]}"
            except Exception:
                pass
        return "无记录"

    def do_scan():
        b = get_base()
        if not b or state["busy"]:
            return
        try:
            state["plan"] = core.scan(b)
            fill_tree()
            chip_pending._value_label.configure(text=str(len(state["plan"])))
            latest = b / ".autoclassifier" / "latest.json"
            btn_undo.configure(state="normal" if latest.exists() else "disabled")
            if not state["plan"]:
                btn_apply.configure(state="disabled")
                status_var.set("桌面很干净，没有需要整理的内容 ✓")
                status.configure(fg=C["success"])
                return
            btn_apply.configure(state="normal")
            unknown = [u for u in state["plan"] if u[1] == core.MISC]
            if ai_ready() and unknown:
                status_var.set(f"规则识别 {len(state['plan']) - len(unknown)} 项，AI 正在识别 {len(unknown)} 项…")
                status.configure(fg=C["warning"])
                set_busy(True)
                threading.Thread(target=ai_worker, args=(b, [u[2] for u in unknown]),
                                 daemon=True).start()
            else:
                status_var.set(f"扫描完成：{len(state['plan'])} 项待整理。点击「🚀 一键分类」执行。")
                status.configure(fg=C["primary"])
        except Exception as e:
            log_app(b, f"扫描异常: {e!r}")
            messagebox.showerror("扫描失败", str(e))

    def ai_worker(b, names):
        try:
            cfg = state["cfg"]
            mapping = llm.classify_names(cfg["base_url"], cfg["api_key"], cfg["model"],
                                         names, core.CATEGORY_FOLDERS)
            q.put(("ai_ok", b, mapping))
        except Exception as e:
            q.put(("ai_fail", b, str(e)))

    def do_apply():
        b = get_base()
        if not b or not state["plan"] or state["busy"]:
            return
        if not messagebox.askyesno(
                "确认一键分类",
                f"将把 {len(state['plan'])} 项移入对应分类文件夹。\n整理后可随时「↩ 撤销上次」，继续吗？"):
            return
        set_busy(True)
        progress.pack(fill="x", pady=(0, 8))
        progress.configure(maximum=len(state["plan"]), value=0)

        def work():
            def on_progress(done, total):
                q.put(("prog", b, (done, total)))
            try:
                moves, failures = core.apply(
                    b, [(p, c, n) for p, c, n, _ in state["plan"]],
                    progress=on_progress, app_dir=b / ".autoclassifier")
                q.put(("apply_ok", b, (moves, failures)))
            except Exception as e:
                q.put(("apply_fail", b, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def apply_done(b, moves, failures):
        progress.pack_forget()
        log_app(b, f"整理完成: 移动{len(moves)} 失败{len(failures)}")
        set_busy(False)
        do_scan()
        if failures:
            status_var.set(f"整理完成，{len(failures)} 项失败")
            status.configure(fg=C["warning"])
            messagebox.showwarning("部分失败", "以下项目移动失败（可能被占用）：\n" +
                                   "\n".join(f"{f['name']}: {f['error']}" for f in failures))
        else:
            status_var.set(f"一键分类完成 ✓ 共整理 {len(moves)} 项")
            status.configure(fg=C["success"])
            messagebox.showinfo("完成", f"已整理 {len(moves)} 项到对应分类文件夹。\n"
                                        "如不满意可点「↩ 撤销上次」一键还原。")

    def do_undo():
        b = get_base()
        if not b or state["busy"]:
            return
        if not messagebox.askyesno("确认撤销", "将把上次整理的所有项目移回原位置，继续吗？"):
            return
        try:
            restored, failures = core.undo(b, app_dir=b / ".autoclassifier")
            log_app(b, f"撤销完成: 还原{len(restored)} 失败{len(failures)}")
            do_scan()
            status_var.set(f"已撤销 ✓ 还原 {len(restored)} 项到原位置")
            status.configure(fg=C["success"])
            if failures:
                messagebox.showwarning("部分还原", "\n".join(failures))
        except Exception as e:
            log_app(b, f"撤销异常: {e!r}")
            messagebox.showerror("撤销失败", str(e))

    def open_folder():
        b = var_path.get().strip()
        if os.path.isdir(b):
            os.startfile(b)

    def pick_dir():
        d = filedialog.askdirectory(initialdir=var_path.get() or str(state["base"]))
        if d:
            var_path.set(d)
            state["cfg"] = load_config(Path(d))
            refresh_ai_chip()
            do_scan()

    # ---------- AI 设置对话框 ----------
    def open_settings():
        cfg = state["cfg"]
        win = tk.Toplevel(root)
        win.title("AI 设置（OpenAI 协议）")
        win.geometry("500x380")
        win.configure(bg=C["bg"])
        win.transient(root)
        win.grab_set()

        box = tk.Frame(win, bg=C["card"], padx=18, pady=18,
                       highlightbackground=C["border"], highlightthickness=1)
        box.pack(fill="both", expand=True, padx=16, pady=16)

        def field(label, show=""):
            tk.Label(box, text=label, bg=C["card"], fg=C["muted"],
                     font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(8, 2))
            e = tk.Entry(box, relief="flat", bg=C["bg"], fg=C["text"],
                         font=("Microsoft YaHei UI", 10), show=show)
            e.pack(fill="x", ipady=4)
            return e

        e_url = field("API 域名（如 https://api.openai.com 或 https://api.deepseek.com，自动补 /v1）")
        e_url.insert(0, cfg.get("base_url", ""))
        e_key = field("API Key（仅保存在本机配置文件，不会上传）", show="•")
        e_key.insert(0, cfg.get("api_key", ""))
        e_model = field("模型名称（如 gpt-4o-mini / deepseek-chat / qwen-plus）")
        e_model.insert(0, cfg.get("model", ""))

        var_enabled = tk.BooleanVar(value=bool(cfg.get("ai_enabled")))
        tk.Checkbutton(box, text="启用 AI 智能分类（仅对规则认不出的项目调用大模型，省 token）",
                       variable=var_enabled, bg=C["card"], fg=C["text"],
                       activebackground=C["card"], font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(10, 4))
        tk.Label(box, text="说明：规则引擎优先，AI 只处理规则无法识别的文件名；分类结果限定在 12 个分类内。",
                 bg=C["card"], fg=C["muted"], font=("Microsoft YaHei UI", 8), wraplength=440,
                 justify="left").pack(anchor="w")

        def do_test():
            url, key, model = e_url.get().strip(), e_key.get().strip(), e_model.get().strip()
            if not (url and key and model):
                messagebox.showwarning("提示", "请先填写域名、Key 和模型名称", parent=win)
                return
            btn_test.configure(state="disabled", text="测试中…")

            def worker():
                try:
                    reply = llm.test_connection(url, key, model)
                    win.after(0, lambda: messagebox.showinfo("连接成功", f"模型回复：{reply}", parent=win))
                except Exception as e:
                    win.after(0, lambda: messagebox.showerror("连接失败", str(e), parent=win))
                finally:
                    win.after(0, lambda: btn_test.configure(state="normal", text="测试连接"))
            threading.Thread(target=worker, daemon=True).start()

        btn_test = tk.Button(box, text="测试连接", command=do_test,
                             bg=C["bg"], fg=C["primary"], activebackground="#E0E9FB",
                             relief="flat", bd=0, padx=16, pady=8, cursor="hand2",
                             font=("Microsoft YaHei UI", 10))
        btn_test.pack(side="left", pady=(12, 0))

        def do_save():
            state["cfg"] = {"base_url": e_url.get().strip(), "api_key": e_key.get().strip(),
                            "model": e_model.get().strip(), "ai_enabled": var_enabled.get()}
            try:
                save_config(state["base"], state["cfg"])
            except Exception as e:
                messagebox.showerror("保存失败", str(e), parent=win)
                return
            refresh_ai_chip()
            win.destroy()
            do_scan()
        tk.Button(box, text="保存并重新扫描", command=do_save,
                  bg=C["primary"], fg="#FFFFFF", activebackground=C["primary_hover"],
                  activeforeground="#FFFFFF", relief="flat", bd=0, padx=20, pady=8,
                  cursor="hand2", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", pady=(12, 0))

    # ---------- 统一事件轮询（AI 结果 + 整理进度） ----------
    def poll_loop():
        try:
            while True:
                kind, b, payload = q.get_nowait()
                if kind == "prog":
                    done, total = payload
                    progress.configure(value=done)
                    status_var.set(f"正在整理… {done}/{total}")
                elif kind == "apply_ok":
                    apply_done(b, payload[0], payload[1])
                elif kind == "apply_fail":
                    progress.pack_forget()
                    set_busy(False)
                    log_app(b, f"整理异常: {payload}")
                    messagebox.showerror("整理失败", payload)
                elif kind == "ai_ok":
                    new_plan, ai_count = [], 0
                    for p, cat, name, src in state["plan"]:
                        if cat == core.MISC and payload.get(name):
                            new_plan.append((p, payload[name], name, "AI"))
                            ai_count += 1
                        else:
                            new_plan.append((p, cat, name, src))
                    state["plan"] = new_plan
                    fill_tree()
                    set_busy(False)
                    status_var.set(f"扫描完成：共 {len(state['plan'])} 项，其中 AI 识别 {ai_count} 项。点击「🚀 一键分类」执行。")
                    status.configure(fg=C["primary"])
                    log_app(b, f"AI 识别完成 {ai_count} 项")
                elif kind == "ai_fail":
                    set_busy(False)
                    status_var.set("AI 识别失败，已回退为纯规则分类（可点「⚙ AI 设置」检查配置）")
                    status.configure(fg=C["warning"])
                    log_app(b, f"AI 识别失败: {payload}")
                    messagebox.showwarning("AI 识别失败",
                                           f"已回退为纯规则分类，不影响使用。\n\n错误信息：\n{payload}")
        except queue.Empty:
            pass
        root.after(120, poll_loop)

    # ---------- 事件接线 + 启动 ----------
    btn_apply.configure(command=do_apply)
    btn_scan.configure(command=do_scan)
    btn_undo.configure(command=do_undo)
    btn_open.configure(command=open_folder)
    btn_ai.configure(command=open_settings)

    refresh_ai_chip()
    do_scan()
    root.after(120, poll_loop)
    root.mainloop()
