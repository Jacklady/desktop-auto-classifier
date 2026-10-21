# 桌面自动分类器 (Desktop Auto Classifier)

> 🧹 一键整理杂乱桌面的 Windows 小工具。**零依赖**（纯 Python 标准库），规则引擎优先，可选接入任何 **OpenAI 协议**大模型做智能分类，整理错了**一键撤销**。

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey) ![Deps](https://img.shields.io/badge/%E4%BE%9D%E8%B5%96-0-brightgreen)

## ✨ 特性

- **🚀 一键分类**：打开即自动扫描，点一下主按钮全部归档
- **🔄 一键撤销**：每次整理自动生成还原清单，反悔随时撤回
- **🤖 可选 AI 智能分类**：填入 OpenAI 协议的域名 / Key / 模型名即可启用，只对规则认不出的文件调用大模型，省 token
- **🛡️ 安全边界**：快捷方式（.lnk/.url）、系统文件、隐藏目录、分类文件夹本身永远不会被移动
- **📦 零依赖**：连 AI 调用都用标准库 urllib 实现，`pip install` 都不需要
- **🖥️ 两种用法**：图形界面（打包成单文件 exe 双击即用）+ 命令行模式

## 📁 内置分类

`学习-课程作业` · `课程设计-毕业设计` · `学生工作-党务团务` · `项目-API对接开发` · `项目-接码验证码` · `项目-电商闲鱼` · `项目-VR-Unity` · `项目-SweetHeart情侣应用` · `软件-工具` · `个人-简历软著` · `媒体-素材` · `杂项-其他`

> 分类名可以在 `classifier/core.py` 的 `CATEGORY_FOLDERS` 里随意增删改，规则同步生效。

## 🚀 快速开始

```bash
# 直接运行图形界面（需要 Python 3.10+，Windows 自带 tkinter）
python main.py

# 命令行模式
python -m classifier --scan          # 预览：只看不动
python -m classifier --apply         # 执行整理
python -m classifier --undo          # 撤销上次整理
python -m classifier --selftest      # 自检
python -m classifier --scan --base "D:\你的桌面路径"
```

## 🤖 接入 AI 智能分类（可选）

界面点 **「⚙ AI 设置」**，填三项并勾选启用：

| 配置项 | 说明 | 示例 |
|---|---|---|
| API 域名 | OpenAI 协议地址，自动补 `/v1` | `https://api.openai.com`、`https://api.deepseek.com`、本地 `http://localhost:11434` |
| API Key | 仅保存在本机 `分类器配置.json`，不会上传 | `sk-...` |
| 模型名称 | 任意 chat 模型 | `gpt-4o-mini`、`deepseek-chat`、`qwen-plus` |

- 点「测试连接」验证配置，成功后保存
- 分类策略：**规则引擎优先**（快、免费），AI 只处理规则认不出的文件名，识别结果在列表中标记为「AI」
- AI 失败自动回退纯规则模式，不影响正常使用

## 📦 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name DesktopAutoClassifier main.py
# 产物在 dist/DesktopAutoClassifier.exe，放到桌面双击即用
```

## 🗂️ 项目结构

```
desktop-auto-classifier/
├── main.py                  # GUI 启动入口
├── classifier/
│   ├── core.py              # 规则引擎：分类/扫描/整理/撤销
│   ├── llm.py               # OpenAI 协议客户端（urllib 零依赖）
│   ├── gui.py               # tkinter 界面
│   └── __main__.py          # 命令行入口
├── 分类器配置.example.json   # AI 配置模板
└── build_exe.py             # 打包脚本
```

## ⚙️ 自定义分类规则

- **精确名称**：`core.py` 的 `EXACT` 字典，文件名 → 分类
- **关键词**：`RULES` 列表，按顺序匹配，先命中先归类
- **扩展名**：`MEDIA_EXT` 集合，媒体文件直接归媒体类
- 兜底：认不出的进「杂项-其他」（启用 AI 时交给大模型判断）

## 📄 License

[MIT](LICENSE)
