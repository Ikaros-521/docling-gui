"""核心域逻辑单元测试（不依赖 docling / GUI，秒级运行）。

运行：pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from docling_gui.core import (  # noqa: E402
    OUTPUT_FORMATS,
    BatchConverter,
    Summary,
    collect_supported_files,
    is_supported_file,
)
from docling_gui.i18n import LANG_EN, LANG_ZH, LANGUAGES, set_language, t  # noqa: E402


# ---------------------------------------------------------------- 扫描过滤
def test_collect_filters_and_skips(tmp_path):
    exts = {"docx", "md"}
    (tmp_path / "a.docx").write_text("x")
    (tmp_path / "~$temp.docx").write_text("x")  # Office 锁文件
    (tmp_path / ".hidden.docx").write_text("x")  # 隐藏文件
    (tmp_path / "b.txt").write_text("x")  # 未勾选格式
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.docx").write_text("x")
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config.docx").write_text("x")  # 隐藏目录内
    imgs = tmp_path / "d_images"
    imgs.mkdir()
    (imgs / "e.docx").write_text("x")  # 本工具导出的图片目录

    files = {p.name for p in collect_supported_files(tmp_path, recursive=True, allowed_exts=exts)}
    assert files == {"a.docx", "c.docx"}


def test_collect_non_recursive(tmp_path):
    exts = {"docx"}
    (tmp_path / "a.docx").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.docx").write_text("x")
    files = list(collect_supported_files(tmp_path, recursive=False, allowed_exts=exts))
    assert [p.name for p in files] == ["a.docx"]


def test_collect_single_file(tmp_path):
    f = tmp_path / "only.docx"
    f.write_text("x")
    files = list(collect_supported_files(f, allowed_exts={"docx"}))
    assert [p.name for p in files] == ["only.docx"]
    # 不支持的扩展名不产出
    g = tmp_path / "only.exe"
    g.write_text("x")
    assert list(collect_supported_files(g, allowed_exts={"docx"})) == []


def test_is_supported_file(tmp_path):
    exts = {"docx", "tar.gz"}
    assert is_supported_file(tmp_path / "a.docx", exts)
    assert not is_supported_file(tmp_path / "a.doc", exts)
    assert is_supported_file(tmp_path / "b.tar.gz", exts)


# ---------------------------------------------------------------- 输出路径
def test_resolve_dst_same_path(tmp_path):
    conv = BatchConverter(out_format="md")
    src = tmp_path / "sub" / "a.docx"
    assert conv._resolve_dst(tmp_path, src, ".md") == src.with_suffix(".md")


def test_resolve_dst_mirror(tmp_path):
    out_dir = tmp_path / "out"
    conv = BatchConverter(out_format="html", out_dir=out_dir)
    root = tmp_path / "docs"
    src = root / "a" / "b.docx"
    assert conv._resolve_dst(root, src, ".html") == out_dir / "a" / "b.html"


def test_resolve_dst_single_file(tmp_path):
    out_dir = tmp_path / "out"
    conv = BatchConverter(out_format="md", out_dir=out_dir)
    root = tmp_path / "a.docx"
    root.write_text("x")  # 真实存在的单文件输入
    assert conv._resolve_dst(root, root, ".md") == out_dir / "a.md"


# ---------------------------------------------------------------- 输出格式
def test_output_formats_suffixes_unique():
    suffixes = [s for s, _ in OUTPUT_FORMATS.values()]
    assert len(suffixes) == len(set(suffixes))


def test_batch_converter_rejects_unknown_format():
    import pytest

    with pytest.raises(ValueError):
        BatchConverter(out_format="xlsx")


# ---------------------------------------------------------------- i18n
def test_i18n_key_parity():
    assert set(LANG_ZH) == set(LANG_EN), "中英文词表键必须一一对应"


def test_i18n_switch_and_format():
    set_language("zh")
    assert t("start") == "开始转换"
    set_language("en")
    assert t("start") == "Start"
    assert t("summary_msg", ok=1, skipped=2, failed=3) == "1 succeeded, 2 skipped, 3 failed"
    set_language("zh")
    assert t("summary_msg", ok=1, skipped=2, failed=3) == "成功 1，跳过 2，失败 3"
    assert [code for code, _ in LANGUAGES] == ["zh", "en"]


def test_i18n_fallback_and_invalid():
    set_language("zh")
    assert t("__no_such_key__") == "__no_such_key__"
    import pytest

    with pytest.raises(ValueError):
        set_language("jp")


# ---------------------------------------------------------------- 数据类
def test_summary_defaults():
    s = Summary()
    assert (s.total, s.ok, s.skipped, s.failed, s.stopped) == (0, 0, 0, 0, False)
    assert s.failed_files == []
