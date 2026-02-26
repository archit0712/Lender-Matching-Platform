"""
Quick manual test — run this to see what pdfplumber extracts from your PDFs.
Usage (from backend/):
    python tests/test_extraction.py path/to/file.pdf
"""
import sys
from pathlib import Path

# Ensure backend root is on path so "app" resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pdf_extractor import extract_pdf

if len(sys.argv) < 2:
    print("Usage: python test_extraction.py <path_to_pdf>")
    sys.exit(1)

result = extract_pdf(sys.argv[1])

print("=" * 60)
print(f"File:       {result.source_filename}")
print(f"Pages:      {result.page_count}")
print(f"Tables:     {len(result.tables)}")
print(f"Text chars: {len(result.raw_text)}")
print("=" * 60)

print("\n── RAW TEXT ──────────────────────────────────────────────")
print(result.raw_text[:2000])  # first 2000 chars
if len(result.raw_text) > 2000:
    print(f"... ({len(result.raw_text) - 2000} more chars)")

print("\n── TABLES ────────────────────────────────────────────────")
for i, table in enumerate(result.tables):
    print(f"\nTable {i+1} ({len(table)} rows):")
    for row in table[:3]:  # show first 3 rows of each table
        print(f"  {row}")
    if len(table) > 3:
        print(f"  ... ({len(table) - 3} more rows)")

print("\n── FULL CONTENT (what gets sent to GPT-4o) ───────────────")
full = result.full_content()
print(full[:3000])
print(f"\n[Total content length: {len(full)} chars]")