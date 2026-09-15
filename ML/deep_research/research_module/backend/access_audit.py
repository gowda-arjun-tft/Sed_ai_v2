"""Observational URL/open-action correspondence, never an access or completion validator."""

from ML.deep_research.domain_decider.backend.publication import ObjectMembers
from .document_records import source_entries
from .source_publication import parse_json


def audit_access(raw, blocks):
    """Preserve source entry positions and distinguish observed opens from unexposed evidence."""
    actions = []
    for position, block in enumerate(blocks):
        if not isinstance(block, dict) or block.get("type") != "web_search_call":
            continue
        action = block.get("action") or {}
        actions.append({"position": position, "id": block.get("id"), "action": action,
                        "status": block.get("status")})
    try:
        entries = list(source_entries(parse_json(raw)))
    except (ValueError, RecursionError):
        entries = []
    observations = []
    for location, entry, ambiguous in entries:
        urls = [value for key, value in entry if key == "url"] if isinstance(entry, ObjectMembers) else []
        for index, url in enumerate(urls):
            matching = [item["position"] for item in actions if isinstance(item["action"], dict)
                        and item["action"].get("type") == "open_page"
                        and isinstance(url, str) and item["action"].get("url") == url]
            observations.append({"entry": location, "url_member": index, "url": url,
                                 "ambiguous": ambiguous or len(urls) != 1,
                                 "open_positions": matching,
                                 "observation": "explicit_open_recorded" if matching else "open_evidence_unavailable"})
    return {"observations": observations, "ordered_actions": actions,
            "limitation": "An open action does not prove readable contents. Missing actions do not prove no attempt occurred."}
