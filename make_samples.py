from pathlib import Path
from app.ingestion.metadata import build_document
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
import pymupdf

Path("extraction-samples").mkdir(exist_ok=True)

def raw_html(p):
    soup = BeautifulSoup(Path(p).read_text(encoding="utf-8", errors="replace"), "html.parser")
    return soup.get_text("\n", strip=True)

def raw_docx(p):
    doc = DocxDocument(p)
    return "\n".join(x.text for x in doc.paragraphs if x.text.strip())

def raw_pdf(p):
    with pymupdf.open(p) as doc:
        return "\n".join(page.get_text() for page in doc)

samples = [
    ("corpus/en/mobile-lines.html", raw_html),
    ("corpus/en/orange-money.docx", raw_docx),
    ("corpus/en/mobile-lines.pdf", raw_pdf),
    ("corpus/ar/mobile-lines.html", raw_html),
    ("corpus/ar/orange-money.docx", raw_docx),
    ("corpus/ar/mobile-lines.pdf", raw_pdf),
]

for path, raw_fn in samples:
    p = Path(path)
    raw_text = raw_fn(p)
    doc = build_document(p)
    out_name = p.stem + "_" + p.suffix.lstrip(".") + "_" + doc["language"] + ".txt"
    out_path = Path("extraction-samples") / out_name
    if doc["status"] == "ok":
        clean_block = doc["text"]
    else:
        clean_block = "[REJECTED] " + str(doc["reject_reason"])
    clean_chars = len(doc["text"]) if doc["status"] == "ok" else 0
    content = "===== RAW (before) =====\n" + raw_text[:2000] + "\n\n"
    content += "===== CLEAN (after) =====\n" + clean_block[:2000] + "\n\n"
    content += "RAW_CHARS=" + str(len(raw_text)) + "  CLEAN_CHARS=" + str(clean_chars) + "  STATUS=" + doc["status"]
    out_path.write_text(content, encoding="utf-8")
    print("saved:", out_path)

print("done")
