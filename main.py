# -*- coding: utf-8 -*-
"""双击/启动入口：python main.py"""
import sys
import traceback
from pathlib import Path


def _log(msg: str):
    try:
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        d = base / ".autoclassifier"
        d.mkdir(parents=True, exist_ok=True)
        import datetime
        with open(d / "运行日志.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        _log(f"程序启动 (frozen={getattr(sys, 'frozen', False)})")
        from classifier.gui import run_gui
        run_gui()
        _log("GUI 正常退出")
    except Exception:
        err = traceback.format_exc()
        _log(f"致命异常:\n{err}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, err[-1500:], "桌面自动分类器 - 出错", 0x10)
        except Exception:
            print(err)
