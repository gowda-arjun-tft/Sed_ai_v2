"""Run-owned upload policy and lossless enrichment of source response objects."""

from urllib.parse import urlsplit, urlunsplit

from ML.deep_research.layer2.backend.publication import ObjectMembers
from .retrieval import normalize_url

REGISTRY_PATH = "_internal/trace/document_uploads.json"
UPLOAD_POLICY = {"version": 2, "enabled": True, "purpose": "user_data",
                 "retention": "until_deleted", "max_bytes": 512_000_000,
                 "max_concurrency": 1, "download_attempts": 3, "read_retries": 2}


def source_entries(value):
    """Yield source values and locations, flagging ambiguous duplicate source collections."""
    if not isinstance(value, ObjectMembers):
        return
    collections = [(i, item) for i, (key, item) in enumerate(value) if key == "sources"]
    for position, items in collections:
        if not isinstance(items, list) or isinstance(items, ObjectMembers):
            yield f"sources/{position}", items, True
            continue
        for index, item in enumerate(items):
            yield f"sources/{position}/{index}", item, len(collections) != 1


def candidate(entry, ambiguous=False):
    """Interpret only explicit, unambiguous document URLs; never infer alternate fields."""
    if not isinstance(entry, ObjectMembers):
        return None, "unprocessed_source"
    documents = [v for k, v in entry if k == "document"]
    urls = [v for k, v in entry if k == "url"]
    if ambiguous or len(documents) > 1 or len(urls) > 1:
        return None, "ambiguous_source"
    if len(documents) != 1 or documents[0] is not True:
        return None, None
    if len(urls) != 1 or not isinstance(urls[0], str):
        return None, "unusable_url"
    try:
        url = urls[0].strip()
        parts = urlsplit(url)
        if (parts.scheme.lower() not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None
                or any(ord(char) < 32 for char in url)):
            raise ValueError("Unsafe URL")
        port = parts.port  # Validate before the shared normalizer can discard an invalid port.
        # Bracket IPv6 explicitly; the legacy normalizer is kept unchanged for Layer 4.
        if ":" in parts.hostname:
            host = f"[{parts.hostname.lower()}]"
            if port and port != (443 if parts.scheme.lower() == "https" else 80):
                host += f":{port}"
            return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, "")), None
        return normalize_url(url), None
    except ValueError:
        return None, "unusable_url"


def enrich(value, registry):
    """Add trusted upload fields without collapsing or rewriting original source members."""
    for _, entry, ambiguous in source_entries(value):
        if not isinstance(entry, ObjectMembers):
            continue
        url, reason = candidate(entry, ambiguous)
        receipt = registry.get("urls", {}).get(url, {})
        uploaded = registry.get("files", {}).get(receipt.get("sha256"), {})
        success = receipt.get("status") == "complete" and uploaded.get("status") == "complete"
        file_id = uploaded.get("file_id") if success else None
        if success and file_id:
            status = "uploaded"
        elif uploaded.get("status") in {"intent", "uncertain"}:
            status = "uncertain"
        elif reason or receipt.get("status") == "failed" or uploaded.get("status") in {"rejected", "unavailable"}:
            status = "failed"
        elif url:
            status = "uncertain"
        else:
            status = "not_applicable"
        # Only these application-owned projection fields replace model-supplied values.
        entry[:] = [(k, v) for k, v in entry if k not in {"upload", "file_id", "upload_status"}]
        entry.extend([("upload_status", status), ("upload", bool(file_id)), ("file_id", file_id)])
    return value


def research_usable(entry):
    """Return whether a derived source entry is safe to supply to future research."""
    if not isinstance(entry, ObjectMembers):
        return False
    fields = {key: [value for name, value in entry if name == key]
              for key in ("url", "document", "access", "upload_status", "file_id")}
    if any(len(values) > 1 for values in fields.values()):
        return False
    if len(fields["url"]) != 1 or not isinstance(fields["url"][0], str) or not fields["url"][0].strip():
        return False
    document = fields["document"][0] if fields["document"] else None
    if document is True:
        file_id = fields["file_id"][0] if fields["file_id"] else None
        return fields["upload_status"] == ["uploaded"] and isinstance(file_id, str) and bool(file_id.strip())
    return (fields["document"] in ([False], [None])
            and fields["upload_status"] == ["not_applicable"]
            and fields["access"] in (["readable"], ["partial"]))
