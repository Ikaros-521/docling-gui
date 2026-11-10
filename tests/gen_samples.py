"""生成全格式测试样例（docling-gui 冻结产物 smoke test 用）。

覆盖无需 LibreOffice/ffmpeg/ASR 的全部常规输入格式：
PDF DOCX PPTX XLSX CSV HTML AsciiDoc EPUB EML ICS VTT LaTeX JATS-XML PNG

用法：python tests/gen_samples.py 输出目录
"""

import csv
import email.mime.multipart
import email.mime.text
import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

_STEMS: list[str] = []


def _add(path: Path) -> Path:
    _STEMS.append(path.stem)
    return path


def gen_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    c.setFont("Helvetica", 16)
    c.drawString(72, 750, "Docling GUI Sample Report")
    c.setFont("Helvetica", 11)
    c.drawString(72, 720, "This PDF exercises the docling-parse text extraction path.")
    c.drawString(72, 700, "Section 1: plain paragraphs with punctuation, numbers 12345.")
    c.drawString(72, 680, "Section 2: a small table below.")
    y = 650
    rows = [("Name", "Qty", "Price"), ("Widget", "3", "9.90"), ("Gadget", "1", "24.50")]
    for row in rows:
        for i, cell in enumerate(row):
            c.drawString(72 + i * 100, y, cell)
        y -= 18
    c.save()


def gen_docx(path: Path) -> None:
    from docx import Document
    from docx.shared import Inches

    doc = Document()
    doc.add_heading("Docx Sample", 0)
    doc.add_heading("Paragraphs", level=1)
    p = doc.add_paragraph("Plain text with ")
    run = p.add_run("bold")
    run.bold = True
    p.add_run(" and ")
    italic = p.add_run("italic")
    italic.italic = True
    doc.add_heading("List", level=1)
    for t in ["alpha", "beta", "gamma"]:
        doc.add_paragraph(t, style="List Bullet")
    doc.add_heading("Table", level=1)
    table = doc.add_table(rows=2, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "A"
    table.rows[0].cells[1].text = "B"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "2"
    tmp_png = path.parent / "_tmp_img.png"
    gen_png(tmp_png)
    doc.add_picture(str(tmp_png), width=Inches(1.5))
    tmp_png.unlink()
    doc.save(str(path))


def gen_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])  # 标题 + 正文
    slide.shapes.title.text = "Pptx Sample Deck"
    tf = slide.placeholders[1].text_frame
    tf.text = "First bullet point"
    for t in ["Second bullet point", "Third bullet point"]:
        p = tf.add_paragraph()
        p.text = t
    prs.save(str(path))


def gen_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Item", "Count"])
    ws.append(["Apples", 4])
    ws.append(["Pears", 7])
    wb.save(str(path))


def gen_csv(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "population"])
        writer.writerow(["Tokyo", "37400068"])
        writer.writerow(["Delhi", "28514000"])


def gen_html(path: Path) -> None:
    path.write_text(
        "<html><head><title>Html Sample</title></head><body>"
        "<h1>Html Sample</h1><p>A paragraph with a "
        "<a href='https://example.com'>link</a>.</p>"
        "<ul><li>one</li><li>two</li></ul>"
        "<table><tr><th>K</th><th>V</th></tr><tr><td>a</td><td>1</td></tr></table>"
        "</body></html>",
        encoding="utf-8",
    )


def gen_adoc(path: Path) -> None:
    path.write_text(
        "= AsciiDoc Sample\n"
        ":author: Docling GUI\n\n"
        "== Section One\n\n"
        "A plain paragraph with *bold* and _italic_.\n\n"
        "== Section Two\n\n"
        "* list one\n"
        "* list two\n",
        encoding="utf-8",
    )


def gen_png(path: Path) -> None:
    Image.new("RGB", (160, 90), (200, 60, 60)).save(path, format="PNG")


def gen_epub(path: Path) -> None:
    """最小合法 EPUB3（mimetype 必须首个且不压缩）。"""
    chapter = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns='http://www.w3.org/1999/xhtml'><head>"
        "<title>Chapter</title></head><body>"
        "<h1>Epub Sample</h1><p>Hello from the packaged book.</p>"
        "</body></html>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            "<?xml version='1.0'?>"
            "<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
            "<rootfiles><rootfile full-path='OEBPS/content.opf' "
            "media-type='application/oebps-package+xml'/></rootfiles></container>",
        )
        zf.writestr(
            "OEBPS/content.opf",
            "<?xml version='1.0'?>"
            "<package xmlns='http://www.idpf.org/2007/opf' version='3.0' unique-identifier='id'>"
            "<metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            "<dc:identifier id='id'>urn:uuid:1234</dc:identifier>"
            "<dc:title>Epub Sample</dc:title>"
            "<dc:language>en</dc:language>"
            "<meta property='dcterms:modified'>2026-01-01T00:00:00Z</meta></metadata>"
            "<manifest><item id='ch1' href='ch1.xhtml' media-type='application/xhtml+xml'/></manifest>"
            "<spine><itemref idref='ch1'/></spine></package>",
        )
        zf.writestr("OEBPS/ch1.xhtml", chapter)


def gen_eml(path: Path) -> None:
    msg = email.mime.multipart.MIMEMultipart()
    msg["From"] = "sender@example.com"
    msg["To"] = "receiver@example.com"
    msg["Subject"] = "Email Sample"
    msg.attach(email.mime.text.MIMEText("This is the plain text body.\nSecond line.", "plain"))
    with open(path, "wb") as f:
        f.write(msg.as_bytes())


def gen_ics(path: Path) -> None:
    path.write_text(
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Docling GUI//Sample//EN\n"
        "BEGIN:VEVENT\n"
        "UID:sample-1@docling-gui\n"
        "DTSTART:20260101T090000Z\n"
        "DTEND:20260101T100000Z\n"
        "SUMMARY:Sample Event\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n",
        encoding="utf-8",
    )


def gen_vtt(path: Path) -> None:
    path.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "Hello from the sample subtitle.\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "Second caption line.\n",
        encoding="utf-8",
    )


def gen_tex(path: Path) -> None:
    path.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Latex Sample}\n"
        "A paragraph with inline math $E=mc^2$.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )


def gen_jats(path: Path) -> None:
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<!DOCTYPE article PUBLIC '-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.2 20120315//EN' "
        "'JATS-journalpublishing1.dtd'>"
        "<article xmlns:xlink='http://www.w3.org/1999/xlink'>"
        "<front><article-meta><title-group>"
        "<article-title>JATS Sample Article</article-title>"
        "</title-group></article-meta></front>"
        "<body><sec><title>Introduction</title>"
        "<p>Paragraph inside a section.</p></sec></body>"
        "</article>",
        encoding="utf-8",
    )


GENERATORS = {
    "pdf": gen_pdf,
    "docx": gen_docx,
    "pptx": gen_pptx,
    "xlsx": gen_xlsx,
    "csv": gen_csv,
    "html": gen_html,
    "adoc": gen_adoc,
    "epub": gen_epub,
    "eml": gen_eml,
    "ics": gen_ics,
    "vtt": gen_vtt,
    "tex": gen_tex,
    "jats": gen_jats,
    "png": gen_png,
}

# png 与图片管线同名（docx 内嵌图片的临时文件已清理，不参与扫描）
EXPECTED_STEMS = ["pdf", "docx", "pptx", "xlsx", "csv", "html", "adoc", "epub", "eml", "ics", "vtt", "tex", "jats", "png"]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/_samples")
    out.mkdir(parents=True, exist_ok=True)
    # JATS 在 docling 中按 .xml/.nxml 扩展名识别，不能用 .jats 后缀
    for stem, fn in GENERATORS.items():
        ext = "xml" if stem == "jats" else stem
        fn(_add(out / f"{stem}.{ext}"))
    print(f"已生成 {len(_STEMS)} 个样例 -> {out}")
    print("期望输出: " + " ".join(f"{s}.md" for s in EXPECTED_STEMS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
