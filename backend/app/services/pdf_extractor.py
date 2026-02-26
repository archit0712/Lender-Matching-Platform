import pdfplumber
from dataclasses import dataclass, field
from pathlib import Path





@dataclass
class ExtractedPDF:
    raw_text: str
    tables: list[list[dict]]
    page_count: int
    source_filename: str


    def full_content(self) -> str:
        parts = [self.raw_text]

        for i, table in enumerate(self.tables):
            if not table:
                continue
            parts.append(f"\n-- TABLE {i+1} --")
            headers = list(table[0].keys())
            parts.append(" | ".join(headers))
            parts.append("-" * 60)

            for row in table:
                parts.append(" | ".join(str(v or "") for v in row.values()))
            
        return "\n".join(parts)


def extract_pdf(file_path: str | Path) -> ExtractedPDF:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"File is not a PDF: {path}")

    text_parts: list[str] = []
    all_tables: list[list[dict]] = []
    
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables()
            table_bboxes = []

            for raw_table in page_tables:
                if not raw_table or len(raw_table) < 2:
                    continue

                headers = [
                    (cell or "").strip() or f"col_{i}"
                    for i, cell in enumerate(raw_table[0])
                ]

                rows = []

                for raw_row in raw_table[1:]:
                    row_dict = {
                        headers[i]: (cell or "").strip() 
                        for i, cell in enumerate(raw_row)
                        if i < len(headers)
                    }

                    if any(v for v in row_dict.values()):
                        rows.append(row_dict)

                if rows:
                    all_tables.append(rows)

                table_bbox = page.find_tables()
                table_bboxes.extend(t.bbox for t in table_bbox)
            
            page_for_text = page

            for bbox in table_bboxes:
                try:
                    page_for_text = page_for_text.outside_bbox(bbox)
                except Exception:
                    continue
            
            text = page_for_text.extract_text(
                x_tolerance=2,
                y_tolerance=2,
            )

            if text and text.strip():
                text_parts.append(f"[Page {page_num}]\n{text.strip()}")

        return ExtractedPDF(
            raw_text="\n\n".join(text_parts),
            tables=all_tables,
            page_count=page_count,
            source_filename=path.name,
        )


def extract_pdf_from_bytes(file_bytes: bytes, filename: str) -> ExtractedPDF:
    """
    Same as extract_pdf() but accepts raw bytes (from a file upload).
    Writes to a temp file, extracts, cleans up.
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        return extract_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)  # always clean up the temp file
        


