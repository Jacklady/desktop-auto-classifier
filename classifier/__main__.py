# -*- coding: utf-8 -*-
"""命令行入口：python -m classifier --scan / --apply / --undo / --selftest"""
import sys
from pathlib import Path

from . import core


def main():
    args = sys.argv[1:]

    def get_base():
        if "--base" in args:
            return Path(args[args.index("--base") + 1])
        # 默认：当前工作目录
        return Path.cwd()

    try:
        if "--selftest" in args:
            import tkinter  # noqa: F401
            from . import llm
            assert core.classify("张三-课程设计报告.pdf") == "课程设计-毕业设计"
            assert core.classify("holiday.jpg") == "媒体-素材"
            assert llm.normalize_base("https://api.openai.com") == "https://api.openai.com/v1"
            assert llm.normalize_base("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1"
            print("selftest OK")
        elif "--scan" in args:
            by = {}
            for p, cat, name, src in core.scan(get_base()):
                by.setdefault(cat, []).append(name)
            total = 0
            for cat in core.CATEGORY_FOLDERS:
                if cat in by:
                    print(f"[{cat}] {len(by[cat])} 项: {', '.join(by[cat])}")
                    total += len(by[cat])
            print(f"共 {total} 项待整理")
        elif "--apply" in args:
            b = get_base()
            moves, failures = core.apply(b, [(p, c, n) for p, c, n, _ in core.scan(b)])
            print(f"移动 {len(moves)} 项，失败 {len(failures)} 项")
            for f in failures:
                print("FAIL:", f)
        elif "--undo" in args:
            restored, failures = core.undo(get_base())
            print(f"还原 {len(restored)} 项，失败 {len(failures)} 项")
            for f in failures:
                print("FAIL:", f)
        elif "--gui" in args or not args:
            from .gui import run_gui
            run_gui()
        else:
            print("用法: python -m classifier [--scan | --apply | --undo | --gui | --selftest] [--base 目录]")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
