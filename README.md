# Docling GUI

递归遍历文件夹（含所有子文件夹），把 **docling 支持的全部格式** 批量转换为
**同路径同名** 的目标格式。基于 [docling](https://github.com/docling-project/docling)
（IBM 开源文档解析引擎），界面使用 [QFluentWidgets](https://qfluentwidgets.com/)（PySide6），
通过 GitHub Actions 自动打包 Windows / macOS / Linux 三平台可执行文件。

## ✨ 特性

- 📂 **递归批量**：选定根目录后递归处理所有子文件夹，输出与源文件同路径同名
- 🔍 **输入格式跟随官方能力**：扫描范围动态取自已安装 docling 的格式映射，支持
  PDF、Office（含旧版 .doc/.xls/.ppt，需 LibreOffice）、HTML、Markdown、图片、
  音频、EPUB、CSV、XML 系列等（详见下表）
- 📤 **五种输出**：Markdown / HTML / JSON（DoclingDocument 无损）/ DocTags XML / 纯文本
- 🖼️ **图片导出**：md/html/json 输出时内嵌图片自动导出到 `<名称>_images/`，相对链接引用
- ⏸️ **可中断**：后台线程运行，随时停止；默认跳过已存在的输出，可断点续转
- 🎨 **Fluent 风格界面**：QFluentWidgets 组件、拖拽文件夹、实时日志与进度
- 💻 **双模式**：GUI + 命令行（`--list-formats` 可查看当前支持的输入扩展名）

## 📥 支持的输入格式（docling 官方清单）

| 格式 | 备注/依赖 |
|---|---|
| PDF | 首次转换自动下载模型（布局/表格/OCR） |
| DOCX / XLSX / PPTX（Office 2007+） | 无需模型，纯解析 |
| DOC / XLS / PPT、RTF（旧版二进制） | 需系统安装 [LibreOffice](https://www.libreoffice.org/) |
| ODT / ODS / ODP（OpenDocument） | 无 |
| EPUB | 无 |
| HTML / XHTML / MHTML | 无 |
| Markdown / AsciiDoc / LaTeX / CSV / 纯文本 | 无 |
| PNG / JPEG / TIFF / BMP / WEBP / GIF | 首次转换自动下载模型（OCR） |
| WAV / MP3 / M4A / AAC / OGG / FLAC（音频） | 需 audio/asr 依赖（本仓库已带），首次下载 ASR 模型 |
| MP4 / AVI / MOV / MKV / WEBM（视频，仅取音轨转写） | 同上，另需系统 ffmpeg |
| Email（.eml / .msg）、iCalendar、WebVTT、BoxNote、USPTO/JATS/XBRL XML、DocLang XML/archive 等 | 无 |
| Pages / Numbers / Keynote | 需 iWork 扩展（默认未启用） |

精确清单以本机为准：`docling-gui --list-formats`。

## 📤 输出格式

| 格式 | 后缀 | 说明 |
|---|---|---|
| Markdown | `.md` | 图片导出为相对链接 |
| HTML | `.html` | 图片导出为相对链接 |
| JSON | `.json` | DoclingDocument 无损结构（图片按引用保存） |
| DocTags | `.doctags` | XML 文档标记（面向训练/RAG 切块场景） |
| 纯文本 | `.txt` | 纯文本导出 |

## 📥 下载

到 [Releases](../../releases) 页面下载对应平台压缩包：

| 文件 | 平台 |
|---|---|
| `docling-gui-windows-x64.zip` | Windows 10+ x64 |
| `docling-gui-macos-arm64.zip` | macOS 12+ Apple Silicon（M1/M2/M3/M4） |
| `docling-gui-linux-x64.zip` | Linux x64 |

解压后运行 `docling-gui`（macOS 为 `docling-gui.app`）。

> **体积说明**：全格式版随包携带 torch/transformers/OCR 栈，压缩包为数 GB 级。
> **macOS 首次打开提示"已损坏"**：右键 → 打开，或 `xattr -cr /path/to/docling-gui.app`。
> **Linux**：图形界面依赖 xcb/xkbcommon 运行库（桌面发行版一般自带），
> 缺失时 `sudo apt install libxcb-cursor0 libxkbcommon0 libegl1`；
> 打包版无控制台，`--cli` 看不到输出，重度命令行用户建议源码运行。

## 🖱️ 使用

### GUI

1. 选择（或直接拖入）根目录
2. 选择输出格式，按需勾选：包含子文件夹 / 覆盖已有输出 / 导出图片
3. 点「开始转换」，日志实时显示每个文件的结果

技巧：把文件夹拖到程序图标上启动会自动填入路径。

### 命令行

```bash
# 递归转换整个文件夹（默认输出 Markdown）
docling-gui D:\docs

# 指定输出格式
docling-gui D:\docs --to html

# 常用参数
--to md|html|json|doctags|txt   输出格式（默认 md）
--overwrite                     覆盖已存在的输出（默认跳过）
--no-images                     不导出内嵌图片
--flat                          不递归子文件夹
--list-formats                  列出当前支持的输入扩展名
--version                       显示版本
```

## ⚠️ 已知限制

- **首次转换 PDF / 图片 / 音频会自动下载模型**到 `~/.cache/docling`（数百 MB，仅一次）
- 旧版 .doc/.xls/.ppt/.rtf 需要系统安装 LibreOffice（`soffice` 在 PATH 或默认安装路径）
- 视频（音轨转写）另需系统 ffmpeg；Pages/Numbers/Keynote 需 iWork 扩展
- 受密码保护/损坏的文件会失败并在日志标出，不影响其他文件
- 图片链接为相对路径，移动输出文件时请连同 `<名称>_images/` 一起移动
- 上一轮生成的输出（如 .md）和 `<名称>_images/` 目录会被扫描器自动跳过，不会循环转换

## 🛠️ 源码运行 / 开发

依赖 Python ≥ 3.10。

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -e .        # Windows
# .venv/bin/pip install -r requirements.txt -e .          # macOS / Linux

python -m docling_gui                 # 启动 GUI
python -m docling_gui D:\docs --cli   # 命令行模式
```

生成多格式测试样例并自测：

```bash
pip install python-docx python-pptx openpyxl pillow   # fixture 生成依赖
python tests/make_fixtures.py tests/_sandbox
python -m docling_gui tests/_sandbox --cli
```

## 🔨 自行打包 / CI 打包

本仓库带 [GitHub Actions 工作流](.github/workflows/build.yml)（`docling-gui.spec` 为
PyInstaller 配置）。两种触发方式：

- **推送版本标签**：`git tag v0.2.0 && git push origin v0.2.0`，构建完成后自动发布 Release
- **手动**：Actions 页面 → Build & Release → Run workflow（产物在 Actions Artifacts）

本地打包：

```bash
pip install pyinstaller
pyinstaller docling-gui.spec --noconfirm
# 产物在 dist/docling-gui/
```

打包要点（踩坑记录，详见 spec 注释）：docling 的插件注册依赖 dist-info 元数据
（`copy_metadata("docling_slim")`）与 entry_points 动态导入的插件模块
（`docling.models.plugins.defaults` 需显式 hiddenimports）；qfluentwidgets 资源需
`collect_all`；easyocr/docling_ibm_models 自带数据文件需收集。

## 🧱 项目结构

```
├── src/docling_gui/
│   ├── core.py        # 动态格式发现 + 递归扫描 + docling 转换（GUI/CLI 共用）
│   ├── app.py         # QFluentWidgets 图形界面（后台线程 + 信号更新）
│   └── __main__.py    # 入口：python -m docling_gui
├── tests/             # 测试样例生成器
├── docling-gui.spec   # PyInstaller 打包配置（三平台共用）
└── .github/workflows/build.yml  # 三平台 CI 打包 + Release
```

## 📄 许可证

[MIT](LICENSE)
