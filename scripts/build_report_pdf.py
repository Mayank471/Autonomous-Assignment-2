"""Builds REPORT.pdf from REPORT.md: Markdown -> HTML (markdown-it) -> PDF (headless Edge or Chrome).

Usage: python scripts/build_report_pdf.py
The LaTeX version (report/report.tex) is an alternative for machines that have a TeX engine.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; line-height: 1.4; color: #111; }
h1 { font-size: 20pt; } h2 { font-size: 15pt; border-bottom: 1px solid #999; padding-bottom: 2px; margin-top: 18pt; }
h3 { font-size: 12pt; } code { font-family: Consolas, monospace; font-size: 8.5pt; background: #f1f1f1; padding: 0 2px; }
pre { background: #f6f6f6; border: 1px solid #ddd; padding: 6px; font-size: 8pt; white-space: pre-wrap; word-break: break-word; }
pre code { background: none; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 8.5pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #999; padding: 3px 5px; vertical-align: top; text-align: left; word-break: break-word; }
th { background: #e8e8e8; }
"""


def main():
    md = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    body = MarkdownIt("commonmark").enable("table").render(md)
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>Academic Helpdesk report</title><style>{CSS}</style></head><body>{body}</body></html>"
    browser = next((b for b in BROWSERS if Path(b).exists()), shutil.which("msedge") or shutil.which("chrome"))
    if not browser:
        sys.exit("No Edge/Chrome found; compile report/report.tex instead.")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "report.html"
        page.write_text(html, encoding="utf-8")
        out = ROOT / "REPORT.pdf"
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", page.as_uri()], check=True, timeout=120)
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
