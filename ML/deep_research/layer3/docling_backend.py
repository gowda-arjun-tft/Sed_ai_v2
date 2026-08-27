"""Small adapter around the pinned local Docling API."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


_MIME_SUFFIX = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
}


def input_suffix(manifest: dict[str, Any]) -> str:
    media_type = str(manifest.get("content_type", "")).partition(";")[0].casefold()
    url_suffix = Path(urlsplit(str(manifest.get("url", ""))).path).suffix.casefold()
    aliases = {".htm": ".html", ".jpeg": ".jpg", ".tif": ".tiff"}
    url_suffix = aliases.get(url_suffix, url_suffix)
    return _MIME_SUFFIX.get(media_type) or (
        url_suffix if url_suffix in set(_MIME_SUFFIX.values()) else ".bin"
    )


def extractor_versions() -> dict[str, str]:
    versions = {}
    for package in ("docling", "easyocr", "torch"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = ""
    return versions


def docling_converter(languages: list[str]):
    """Build Docling lazily so ordinary imports and offline fakes stay lightweight."""
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as error:
        raise RuntimeError("Docling with the EasyOCR extra is not installed") from error

    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = True
    pipeline.ocr_options = EasyOcrOptions(lang=languages)
    options = {
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
        InputFormat.IMAGE: PdfFormatOption(pipeline_options=pipeline),
    }
    return DocumentConverter(format_options=options)


def convert_docling(
    converter: Any,
    path: Path,
    page_range: tuple[int, int] | None,
) -> tuple[dict[int, str], dict[str, Any], list[str]]:
    kwargs = {"page_range": page_range} if page_range is not None else {}
    result = converter.convert(path, **kwargs)
    raw_status = getattr(result, "status", "success")
    status = str(getattr(raw_status, "value", raw_status)).casefold()
    errors = [
        str(getattr(error, "error_message", error))
        for error in getattr(result, "errors", ())
    ]
    if status not in {"", "success", "partial_success"}:
        detail = f": {'; '.join(errors)}" if errors else ""
        raise RuntimeError(f"Docling conversion status was {status}{detail}")
    if status == "partial_success" and not errors:
        errors.append("Docling reported partial_success")
    document = result.document
    payload = document.export_to_dict()
    keys = sorted(int(number) for number in getattr(document, "pages", {}) or {})
    start = page_range[0] if page_range else 1
    if not keys:
        text = document.export_to_markdown()
        return ({start: text} if text.strip() else {}), payload, errors
    pages = {
        key: document.export_to_markdown(page_no=key)
        for key in keys
    }
    return {number: text for number, text in pages.items() if text.strip()}, payload, errors
