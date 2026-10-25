"""Extract, chunk, embed and index the collected documents into ChromaDB.

1. Text extraction per page (PyMuPDF). Pages without a text layer (scanned
   circulars) are OCR'd with Tesseract. Spreadsheets are read sheet by sheet.
   Extracted pages are cached in data/text/<doc_id>.json for inspection.
2. Chunking within a page (~450 words, 80-word overlap) so every chunk keeps
   an exact page reference for citation.
3. Embedding with the local Ollama model (nomic-embed-text, with its
   "search_document:" task prefix) and storage in data/chroma.

Usage: python scripts/ingest.py [--reextract]
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import chromadb
import ollama
import openpyxl
import pymupdf
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpdesk.config import (CHROMA_COLLECTION, CHROMA_DIR, DATA_DIR, EMBED_MODEL, EMBED_OPTIONS,  # noqa: E402
                             ROOT, SOURCES_CSV)

TEXT_DIR = DATA_DIR / "text"
CHUNK_WORDS, OVERLAP_WORDS = 450, 80
MIN_CHARS_FOR_TEXT_LAYER = 50
# Spreadsheet sheets that hold student personal data are never indexed.
SKIP_SHEETS = re.compile(r"section and group", re.I)
# Structured sources are served through lookup tools (faculty.csv, catalogue.csv, teaching.csv) instead.
SKIP_CATEGORIES = {"faculty-directory", "course-catalogue", "teaching-history"}


def find_tesseract() -> str:
    exe = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if not Path(exe).exists():
        raise SystemExit("Tesseract not found; install it to OCR scanned PDFs (see README).")
    return exe


def ocr_page(page) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "page.png"
        page.get_pixmap(dpi=300).save(img)
        out = subprocess.run([find_tesseract(), str(img), "-", "--psm", "3"],
                             capture_output=True, text=True, encoding="utf-8")
        return out.stdout


def extract_pdf(path: Path):
    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            text, method = page.get_text(), "text"
            if len(text.strip()) < MIN_CHARS_FOR_TEXT_LAYER:
                text, method = ocr_page(page), "ocr"
            pages.append({"page": i + 1, "text": text, "method": method})
    return pages


def extract_html(path: Path):
    """Main text of a saved web page (navigation, header and footer removed) as one page."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = re.sub(r"###\S+###|\S*RedirectToLoginPage\S*", " ", soup.get_text("\n"))
    text = text.split("Important links")[0]  # drop the site-wide footer link list
    return [{"page": 1, "text": re.sub(r"\n\s*\n+", "\n", text).strip(), "method": "html"}]


def extract_xlsx(path: Path):
    pages = []
    wb = openpyxl.load_workbook(path, data_only=True)
    for n, ws in enumerate(wb.worksheets, start=1):
        if SKIP_SHEETS.search(ws.title):
            continue
        lines = [f"Sheet: {ws.title}"]
        for row in ws.iter_rows(values_only=True):
            vals = [" ".join(str(v).split()) for v in row if v not in (None, "")]
            if vals:
                lines.append(" | ".join(vals))
        pages.append({"page": n, "text": "\n".join(lines), "method": f"sheet:{ws.title}"})
    return pages


def chunk_page(text: str):
    words = text.split()
    if not words:
        return []
    step = CHUNK_WORDS - OVERLAP_WORDS
    return [" ".join(words[s:s + CHUNK_WORDS]) for s in range(0, max(len(words) - OVERLAP_WORDS, 1), step)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reextract", action="store_true", help="ignore cached text in data/text/")
    args = ap.parse_args()

    with open(SOURCES_CSV, encoding="utf-8") as f:
        sources = [r for r in csv.DictReader(f)
                   if r["status"] == "ok" and r["category"] not in SKIP_CATEGORIES]
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    ids, docs, metas = [], [], []
    for src in sources:
        path = ROOT / src["local_file"]
        cache = TEXT_DIR / f"{src['doc_id']}.json"
        if cache.exists() and not args.reextract:
            pages = json.loads(cache.read_text(encoding="utf-8"))
        else:
            extract = {".pdf": extract_pdf, ".html": extract_html}.get(path.suffix, extract_xlsx)
            pages = extract(path)
            cache.write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
        n_before = len(ids)
        for p in pages:
            for j, chunk in enumerate(chunk_page(p["text"])):
                ids.append(f"{src['doc_id']}-p{p['page']}-c{j}")
                docs.append(chunk)
                metas.append({"doc_id": src["doc_id"], "title": src["title"], "url": src["url"],
                              "category": src["category"], "page": p["page"], "extraction": p["method"]})
        ocr = sum(p["method"] == "ocr" for p in pages)
        print(f"{src['doc_id']:4} pages={len(pages):3} ocr_pages={ocr:2} chunks={len(ids) - n_before:4}  {src['title'][:60]}")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    col = client.create_collection(CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})

    B = 32
    for s in range(0, len(docs), B):
        batch = docs[s:s + B]
        # the title is prepended so retrieval can also match on the document name
        inputs = [f"search_document: {metas[s + k]['title']} (page {metas[s + k]['page']})\n{t}"
                  for k, t in enumerate(batch)]
        emb = ollama.embed(model=EMBED_MODEL, input=inputs, options=EMBED_OPTIONS)["embeddings"]
        col.add(ids=ids[s:s + B], documents=batch, metadatas=metas[s:s + B], embeddings=emb)
        print(f"  embedded {min(s + B, len(docs))}/{len(docs)}", end="\r")
    print(f"\nIndexed {len(docs)} chunks from {len(sources)} documents into {CHROMA_DIR}")


if __name__ == "__main__":
    main()
