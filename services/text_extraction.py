"""从上传的 PDF / TXT / DOCX 文件中提取纯文本。

页面只调用 extract_text()，解析库细节和错误处理都收敛在本模块。
所有失败均抛出 TextExtractionError，消息为友好中文，可直接展示给用户。
"""

import io

MAX_CONTENT_CHARS = 200_000  # 防止超大文本撑爆数据库

SUPPORTED_EXTENSIONS = ("pdf", "txt", "docx")


class TextExtractionError(Exception):
    """文本提取失败，消息为友好中文，可直接展示给用户。"""


def extract_text(file_bytes, file_ext):
    """按扩展名分发到对应解析器，返回提取出的纯文本。"""
    ext = (file_ext or "").lower().lstrip(".")
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    if ext in ("txt", "md"):
        return _extract_txt(file_bytes)
    if ext == "docx":
        return _extract_docx(file_bytes)
    raise TextExtractionError("暂不支持该文件类型，请上传 PDF、TXT 或 DOCX 文件。")


def _clean(text):
    text = (text or "").strip()
    if not text:
        raise TextExtractionError(
            "未能从文件中提取到任何文本。若这是扫描件或图片版文件，"
            "暂不支持 OCR 识别，请直接粘贴文本内容。"
        )
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS] + "\n\n（内容过长，已截断保留前 20 万字）"
    return text


def _extract_pdf(file_bytes):
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise TextExtractionError("服务器缺少 pypdf 依赖，无法解析 PDF。") from error

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            raise TextExtractionError("该 PDF 已加密，暂不支持解析，请提供未加密版本。")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except TextExtractionError:
        raise
    except Exception as error:
        raise TextExtractionError("PDF 文件可能已损坏或格式异常，无法解析。") from error
    return _clean("\n".join(pages))


def _extract_docx(file_bytes):
    try:
        import docx
    except ImportError as error:
        raise TextExtractionError("服务器缺少 python-docx 依赖，无法解析 DOCX。") from error

    try:
        document = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in document.paragraphs]
        tables = [
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        ]
    except Exception as error:
        raise TextExtractionError("DOCX 文件可能已损坏或格式异常，无法解析。") from error
    return _clean("\n".join(paragraphs + tables))


def _extract_txt(file_bytes):
    text = None
    for encoding in ("utf-8", "gbk"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise TextExtractionError(
            "TXT 文件编码无法识别，请另存为 UTF-8 后重新上传，或直接粘贴文本。"
        )
    return _clean(text)
