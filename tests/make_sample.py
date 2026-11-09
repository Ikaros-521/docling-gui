"""生成测试用示例 docx（含标题/加粗/列表/表格/图片）。

用法：python tests/make_sample.py 输出目录
"""

import sys
from pathlib import Path

from docx import Document
from docx.shared import Inches
from PIL import Image


def make(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    doc.add_heading("测试文档：批量转换示例", 0)

    doc.add_heading("一、普通段落", level=1)
    p = doc.add_paragraph("这是普通段落，包含 ")
    run = p.add_run("加粗文本")
    run.bold = True
    p.add_run(" 与 ")
    italic = p.add_run("斜体文本")
    italic.italic = True
    p.add_run("，docling 应保留为 Markdown 强调语法。")

    doc.add_heading("二、列表", level=1)
    for text in ["第一项", "第二项", "第三项"]:
        doc.add_paragraph(text, style="List Bullet")

    doc.add_heading("三、表格", level=1)
    table = doc.add_table(rows=3, cols=3)
    table.style = "Table Grid"
    header = ["姓名", "年龄", "城市"]
    for col, text in enumerate(header):
        table.rows[0].cells[col].text = text
    data = [["张三", "28", "北京"], ["李四", "32", "上海"]]
    for r, row_data in enumerate(data, start=1):
        for c, text in enumerate(row_data):
            table.rows[r].cells[c].text = text

    doc.add_heading("四、图片", level=1)
    tmp_png = path.parent / "_tmp_img.png"
    Image.new("RGB", (160, 90), (200, 60, 60)).save(tmp_png)
    doc.add_picture(str(tmp_png), width=Inches(1.5))
    tmp_png.unlink()

    doc.save(str(path))


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample.docx")
    make(out)
    print(f"已生成 {out}")
