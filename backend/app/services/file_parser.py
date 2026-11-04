import io


def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF."""
    import fitz

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    return "\n".join(text_parts)


def parse_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def parse_excel(file_bytes: bytes) -> dict:
    """Parse Excel file and extract structured data."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    result = {}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        headers = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(c) if c else f"col_{j}" for j, c in enumerate(row)]
            else:
                row_data = {}
                for j, cell in enumerate(row):
                    if j < len(headers):
                        row_data[headers[j]] = cell
                rows.append(row_data)
        result[sheet_name] = rows

    return result


def parse_excel_to_text(file_bytes: bytes) -> str:
    """Parse Excel and return as formatted text."""
    data = parse_excel(file_bytes)
    parts = []
    for sheet_name, rows in data.items():
        parts.append(f"【{sheet_name}】")
        for row in rows[:50]:
            parts.append(" | ".join(f"{k}: {v}" for k, v in row.items() if v is not None))
    return "\n".join(parts)


ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "docx", "xls", "xlsx", "txt", "md"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def validate_upload(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: .{ext}")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("文件大小超过限制（50MB）")
    validate_file_signature(file_bytes, ext)
    return ext


def validate_file_signature(file_bytes: bytes, ext: str) -> None:
    """Reject files whose magic bytes do not match the claimed extension."""
    ext = ext.lower()
    if ext == "pdf" and not file_bytes.startswith(b"%PDF"):
        raise ValueError("文件内容不是有效的 PDF")
    if ext in ("docx", "xlsx") and not file_bytes.startswith(b"PK"):
        raise ValueError(f"文件内容不是有效的 .{ext}")
    if ext == "xls" and not file_bytes.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValueError("文件内容不是有效的 .xls")


def parse_file(file_bytes: bytes, filename: str) -> str:
    """Parse file based on extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext == "docx":
        return parse_docx(file_bytes)
    elif ext in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore")
    elif ext in ("xlsx", "xls"):
        return parse_excel_to_text(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")
