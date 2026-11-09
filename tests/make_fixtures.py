"""生成多格式测试样例（docx/pptx/xlsx/html/md/csv/png/pdf）。

用法：python tests/make_fixtures.py 输出目录
依赖：python-docx python-pptx openpyxl pillow（均为测试专用，非运行时依赖）
"""

import sys
from pathlib import Path

from PIL import Image


def make_docx(path: Path) -> None:
    from docx import Document
    from docx.shared import Inches

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading("Word 测试文档", 0)
    doc.add_heading("段落与强调", level=1)
    p = doc.add_paragraph("包含 ")
    r = p.add_run("加粗")
    r.bold = True
    p.add_run(" 与 ")
    i = p.add_run("斜体")
    i.italic = True
    doc.add_heading("列表", level=1)
    for t in ["第一项", "第二项"]:
        doc.add_paragraph(t, style="List Bullet")
    doc.add_heading("表格", level=1)
    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "名称"
    table.rows[0].cells[1].text = "值"
    table.rows[1].cells[0].text = "示例"
    table.rows[1].cells[1].text = "42"
    tmp = path.parent / "_tmp.png"
    Image.new("RGB", (120, 80), (60, 120, 200)).save(tmp)
    doc.add_picture(str(tmp), width=Inches(1.2))
    tmp.unlink()
    doc.save(str(path))


def make_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Pt

    path.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "PPT 测试"
    body = slide.placeholders[1]
    tf = body.text_frame
    tf.text = "第一页要点"
    for t in ["要点 A", "要点 B"]:
        para = tf.add_paragraph()
        para.text = t
        para.font.size = Pt(18)
    prs.save(str(path))


def make_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    ws.append(["姓名", "分数"])
    ws.append(["张三", 95])
    ws.append(["李四", 88])
    wb.save(str(path))


def make_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>HTML 测试</title></head>
<body>
<h1>HTML 测试页</h1>
<p>这是一个 <b>HTML</b> 段落，包含<a href="#">链接</a>。</p>
<ul><li>条目一</li><li>条目二</li></ul>
<table><tr><th>列1</th><th>列2</th></tr><tr><td>a</td><td>b</td></tr></table>
</body></html>""",
        encoding="utf-8",
    )


def make_others(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "note.md").write_text("# Markdown 笔记\n\n- 已是 markdown\n- 应保持语义\n", encoding="utf-8")
    (root / "data.csv").write_text("name,age\n张三,28\n李四,32\n", encoding="utf-8")
    img = Image.new("RGB", (200, 120), (240, 180, 60))
    img.save(root / "photo.png")
    img.save(root / "scan.pdf", "PDF", resolution=72)


def main(out_root: str) -> None:
    root = Path(out_root)
    make_docx(root / "目录一" / "report.docx")
    make_docx(root / "目录一" / "目录二" / "深层的.docx")
    make_pptx(root / "目录一" / "deck.pptx")
    make_xlsx(root / "目录二" / "sheet.xlsx")
    make_html(root / "目录二" / "page.html")
    make_others(root)
    print(f"fixtures 已生成于 {root}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/_sandbox")
