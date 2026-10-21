# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本：python build_exe.py"""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", "DesktopAutoClassifier",
        "main.py",
    ])
    print("打包完成，产物在 dist/DesktopAutoClassifier.exe")
