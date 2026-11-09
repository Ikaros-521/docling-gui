# Word 批量转 Markdown（docx2md）

递归遍历文件夹（含所有子文件夹），把所有 `.docx` 转成 **同路径同名** 的 `.md`。
基于 [docling](https://github.com/docling-project/docling)（IBM 开源文档解析引擎），
提供跨平台图形界面，通过 GitHub Actions 自动打包 Windows / macOS / Linux 三平台可执行文件。

## ✨ 特性

- 📂 **递归批量**：选定根目录后递归处理所有子文件夹，`.md` 与源文件同路径同名字
- 🔍 **高质量解析**：docling 的 MSWord 后端，保留标题层级、加粗/斜体、列表、表格、代码块
- 🖼️ **图片导出**：内嵌图片自动导出到 `<同名>_images/`，Markdown 中为相对链接
- 🧮 **公式**：Word 公式（OMML）尽量转为 LaTeX
- ⏸️ **可中断**：转换在后台线程运行，可随时停止；默认跳过已存在的 `.md`，可断点续转
- 💻 **双模式**：GUI（PySide6）+ 命令行，无网络依赖、不下载任何 AI 模型
- 📦 **开箱即用**：Releases 提供三平台压缩包，解压即用

## 📥 下载

到 [Releases](../../releases) 页面下载对应平台压缩包：

| 文件 | 平台 |
|---|---|
| `docx2md-windows-x64.zip` | Windows 10+ x64 |
| `docx2md-macos-arm64.zip` | macOS 12+ Apple Silicon（M1/M2/M3/M4） |
| `docx2md-linux-x64.zip` | Linux x64 |

解压后运行 `docx2md`（macOS 为 `docx2md.app`）。

> **macOS 首次打开提示"已损坏"或无法验证开发者**：右键 `docx2md.app` → 打开；
> 或终端执行 `xattr -cr /path/to/docx2md.app`。这是未签名应用的常见提示，非病毒。
>
> **Linux**：图形界面依赖系统的 xcb/xkbcommon 运行库（多数桌面发行版自带），
> 缺失时 `sudo apt install libxcb-cursor0 libxkbcommon0 libegl1` 即可。
> 打包版为无控制台程序，`--cli` 模式看不到打印输出，重度命令行用户建议源码运行。

## 🖱️ 使用

### GUI

1. 选择（或直接拖入）根目录
2. 按需勾选：覆盖已有 `.md`、导出图片、包含子文件夹
3. 点「开始转换」，日志实时显示每个文件的结果

小技巧：把文件夹拖到 exe/程序图标上，会直接带路径启动 GUI。

### 命令行

```bash
# 递归转换整个文件夹（同路径输出 .md）
docx2md D:\docs

# 常用参数
--overwrite     覆盖已存在的 .md（默认跳过）
--no-images     不导出内嵌图片
--flat          不递归子文件夹
--cli           强制命令行模式（拖拽启动 exe 时默认进 GUI，加此参数走命令行）
--version       显示版本
```

## ⚠️ 已知限制

- **旧版 `.doc`（97-2003 二进制格式）不受支持**：docling 只解析 `.docx`，程序会跳过
  `.doc` 并提示；请先用 Word/WPS 另存为 `.docx`
- 受密码保护/损坏的文件会转换失败并在日志中标出，不影响其他文件
- 图片链接为相对路径，移动 `.md` 时请连同 `<同名>_images/` 一起移动

## 🛠️ 源码运行 / 开发

依赖 Python ≥ 3.10。

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -e .        # Windows
# .venv/bin/pip install -r requirements.txt -e .          # macOS / Linux

python -m docx2md_gui                 # 启动 GUI
python -m docx2md_gui D:\docs --cli   # 命令行模式
```

生成测试样例并自测：

```bash
python tests/make_sample.py tests/_sandbox/sample.docx
python -m docx2md_gui tests/_sandbox --cli
```

## 🔨 自行打包 / CI 打包

本仓库带 [GitHub Actions 工作流](.github/workflows/build.yml)（`docx2md.spec` 为
PyInstaller 配置）。两种触发方式：

- **推送版本标签**：`git tag v0.1.0 && git push origin v0.1.0`，构建完成后自动发布 Release
- **手动**：Actions 页面 → Build & Release → Run workflow（产物在 Actions Artifacts）

> 打包体积说明：docling 依赖 torch 等深度学习栈，但 docx 解析用不到（相关导入均有
> ImportError 保护），spec 已将其排除，产物为百 MB 级而非数 GB。

本地打包：

```bash
pip install pyinstaller
pyinstaller docx2md.spec --noconfirm
# 产物在 dist/docx2md/
```

## 🧱 项目结构

```
├── src/docx2md_gui/
│   ├── core.py        # 递归扫描 + docling 转换（无 GUI 依赖，GUI/CLI 共用）
│   ├── app.py         # PySide6 图形界面（后台线程 + 信号更新）
│   └── __main__.py    # 入口：python -m docx2md_gui
├── tests/make_sample.py  # 生成测试用 docx
├── docx2md.spec       # PyInstaller 打包配置（三平台共用）
└── .github/workflows/build.yml  # 三平台 CI 打包 + Release
```

## 📄 许可证

[MIT](LICENSE)
